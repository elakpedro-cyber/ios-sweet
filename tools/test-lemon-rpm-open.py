"""Exercise actual GLINK open code against a modeled RPM peer; no rail requests."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree / 'bsd/dev/lemon_rpm.c').read_text()
assert '#include <kern/clock.h>' in source, 'delay() requires the XNU clock header'
clock_header = (tree / 'osfmk/kern/clock.h').read_text()
delay_decl = re.search(r'extern void delay\(int usec\);', clock_header).group()
source = re.sub(r'^#include <[^>]+>\n', '', source, flags=re.M)
header = '''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
typedef uintptr_t vm_offset_t, vm_size_t;
'''
header += delay_decl + '\n'
mock = re.sub(r'static void\nlr_write\(.*?\n}\n',
              'static void lr_write(vm_offset_t, unsigned, uint32_t);\n', source, flags=re.S)
assert mock != source
mock = re.sub(r'^\s*__asm__ volatile\([^\n]+\);', '', mock, flags=re.M)
test = r'''
static uint32_t ram[LR_SIZE/4], box[0x1000/4];
static unsigned scenario, writes, delays, complete, tx_commands, fail_map, reverse, suspend_peer;
static struct lr_pipe tx={0x200,0x6f8},rx={0x900,0x6f8};
vm_offset_t ml_io_map(vm_offset_t pa,vm_size_t size) {
    if(pa==LR_PA) {assert(size==LR_SIZE);return fail_map==1?0:(uintptr_t)ram;}
    assert(pa==LR_MBOX_PA && size==0x1000);return fail_map==2?0:(uintptr_t)box;
}
void delay(int us) {assert(us==100);delays++;}
static unsigned used(struct lr_pipe p) {
    unsigned t=ram[p.offset/4],h=ram[p.offset/4+1];
    return h>=t?h-t:p.size-t+h;
}
static void remote(unsigned cmd,unsigned id,unsigned parameter,const char *name) {
    uint32_t packet[6]={cmd|(id<<16),parameter,0,0,0,0};
    unsigned length=name?24:8;
    if(name) memcpy(packet+2,name,13);
    assert(rx.size-used(rx)>=length+8);
    unsigned h=ram[rx.offset/4+1];
    for(unsigned i=0;i<length;i+=4) ram[(rx.offset+8+(h+i)%rx.size)/4]=packet[i/4];
    ram[rx.offset/4+1]=(h+length)%rx.size;
}
static void peer(void) {
    while(used(tx)) {
        unsigned t=ram[tx.offset/4];
        unsigned word=ram[(tx.offset+8+t)/4],cmd=word&0xffff,id=word>>16;
        unsigned param=ram[(tx.offset+8+(t+4)%tx.size)/4];
        unsigned length=cmd==2?24:8;
        assert(used(tx)>=length);tx_commands++;
        assert(cmd==0 || cmd==1 || cmd==2 || cmd==4); /* no data/rail packets */
        ram[tx.offset/4]=(t+length)%tx.size;
        if(cmd==0) {
            assert(id==1 && param==0);
            if(scenario==1) continue; /* silent remote */
            if(scenario==2) {remote(1,0,0,0);continue;}
            remote(0,1,0,0);remote(1,1,0,0);
        } else if(cmd==1) {assert(id==1 && !param);
        } else if(cmd==2) {
            assert(id==1 && param==13);
            char name[16]={0};
            for(unsigned i=0;i<16;i+=4) {
                uint32_t v=ram[(tx.offset+8+(t+8+i)%tx.size)/4];memcpy(name+i,&v,4);
            }
            assert(!strcmp(name,"rpm_requests"));
            if(scenario==3) {remote(4,2,0,0);continue;}
            if(scenario==4) {remote(2,7,13,"bad_requests");continue;}
            if(scenario==5) {remote(2,7,0xffff,0);continue;}
            if(reverse) remote(2,7,13,"rpm_requests");
            remote(4,1,scenario==6?1:0,0);
            if(!reverse) remote(2,7,13,"rpm_requests");
        } else {assert(id==7 && !param);complete++;}
    }
}
static void lr_write(vm_offset_t base,unsigned offset,uint32_t value) {
    writes++;
    if(base==(uintptr_t)box) {
        assert(offset==8 && value==1);box[2]=value;if(!suspend_peer)peer();return;
    }
    assert(base==(uintptr_t)ram && !(offset&3));
    assert(offset==tx.offset+4 || offset==rx.offset ||
           (offset>=tx.offset+8 && offset<tx.offset+8+tx.size));
    if(offset==tx.offset+4 || offset==rx.offset) assert(value<tx.size && !(value&7));
    ram[offset/4]=value;
}
static void setup(unsigned mode) {
    memset(ram,0,sizeof(ram));memset(box,0,sizeof(box));
    writes=delays=complete=tx_commands=fail_map=reverse=suspend_peer=0;scenario=mode;
    ram[LR_TOC/4]=0x67727430;ram[LR_TOC/4+1]=2;
    unsigned p=LR_TOC/4+2;
    ram[p]=LR_TX;ram[p+1]=tx.offset;ram[p+2]=tx.size;
    ram[p+3]=LR_RX;ram[p+4]=rx.offset;ram[p+5]=rx.size;
}
static struct lr_link link_state(void) {
    struct lr_link link={.base=(uintptr_t)ram,.mbox=(uintptr_t)box,.tx=tx,.rx=rx};return link;
}
int main(void) {
    setup(0);struct lr_link link=link_state();assert(lr_handshake(&link));assert(complete==1 && tx_commands==4);
    setup(0);reverse=1;link=link_state();assert(lr_handshake(&link));assert(complete==1);
    setup(6);link=link_state();assert(lr_handshake(&link));assert(complete==1);
    setup(6);reverse=1;link=link_state();assert(lr_handshake(&link));assert(complete==1);
    for(unsigned mode=1;mode<=5;mode++) {
        setup(mode);link=link_state();assert(!lr_handshake(&link));assert(!complete);
        if(mode==1) assert(delays==LR_OPEN_POLLS);
    }
    setup(0);ram[tx.offset/4+1]=8;link=link_state();assert(!lr_handshake(&link) && !writes);
    setup(0);ram[rx.offset/4+1]=8;link=link_state();assert(!lr_handshake(&link) && !writes);
    setup(0);fail_map=1;lemon_rpm_open();assert(!writes);
    setup(0);fail_map=2;lemon_rpm_open();assert(!writes);
    setup(0);ram[LR_TOC/4]=0;lemon_rpm_open();assert(!writes);
    setup(0);lemon_rpm_open();assert(complete==1);
    /* Full TX must fail before any writes. Wrap must preserve packet bytes. */
    setup(1);link=link_state();ram[tx.offset/4+1]=tx.size-8;
    assert(!lr_send(&link,0,1,0,0) && !writes);
    setup(1);link=link_state();ram[tx.offset/4]=24;ram[tx.offset/4+1]=tx.size-8;
    suspend_peer=1;
    assert(lr_send(&link,2,1,13,"rpm_requests"));
    assert(ram[tx.offset/4+1]==16);
    assert(ram[(tx.offset+8+tx.size-8)/4]==0x10002);
    char wrapped[16]={0};memcpy(wrapped,&ram[(tx.offset+8)/4],16);
    assert(!strcmp(wrapped,"rpm_requests"));
    setup(0);link=link_state();link.version_ack=link.open_sent=true;
    ram[rx.offset/4]=ram[rx.offset/4+1]=rx.size-8;
    remote(2,7,13,"rpm_requests");
    assert(lr_receive(&link)==1 && link.remote_id==7 && ram[rx.offset/4]==16);
    /* A partial OPEN must not advance tail. */
    setup(0);link=link_state();link.version_ack=link.open_sent=true;
    remote(2,7,13,"rpm_requests");ram[rx.offset/4+1]=8;
    assert(lr_receive(&link)==0 && ram[rx.offset/4]==0 && !writes);
    puts("PASS: actual GLINK handshake, both OPEN orders, malformed/version/channel IDs, timeout, fresh handoff, FIFO space, partial frame, mapping failures; write whitelist and no data/rail requests");
}
'''
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    (folder/'full.c').write_text(header+source)
    (folder/'test.c').write_text(header+mock+test)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['cc', *flags, '-fsanitize=address,undefined', str(folder/'test.c'), '-o', str(folder/'test')], check=True)
    subprocess.run([str(folder/'test')], check=True)
    cross = shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        subprocess.run([cross, *flags, '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics',
                        '-c', str(folder/'full.c'), '-o', str(folder/'arm64.o')], check=True)
        print('PASS: actual GLINK open ARMv8.0 cross-compile')
