"""Exercise actual bounded sensor readiness checks, including page restoration."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu',type=Path,required=True)
args=parser.parse_args()
text=(args.xnu/'bsd/dev/lemon_touch.c').read_text()
start=text.index('static bool\nlt_identify(')
helper=text[start:text.index('\n}\n',start)+3]
assert 'if (!lt_identify())' in text
program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define LT_EVENT 0x21c00u
static struct {unsigned irq;} lt;
static unsigned tries,waits,page,phase,mode,calls;
static int lt_page(unsigned address) {
    assert(address==LT_EVENT || address==LT_EVENT+0x9a);calls++;
    page=address;
    if(address==LT_EVENT && !phase) {tries++;phase=1;}
    else if(address==LT_EVENT+0x9a) assert(phase==4),phase=5;
    else assert(phase==6),phase=0;
    return mode==5 && tries==1 ? 5 : 0;
}
static int lt_read(unsigned offset,uint8_t *data,unsigned len) {
    calls++;
    if(offset==0x60) {assert(phase==1 && len==5 && page==LT_EVENT);phase=2;data[0]=0xa0;return 0;}
    if(offset==0x78) {
        assert(page==LT_EVENT);
        if(len==2) assert(phase==2),phase=3;
        else assert(len==16 && phase==3),phase=4;
        bool ready=mode==0 || (mode==1 && tries==3);
        if(ready) {
            data[0]=5;data[1]=250;
            if(len==16) {data[4]=4;data[5]=0x38;data[6]=9;data[7]=0x24;}
            if(mode==0 && len==2 && tries==1) data[0]=4; /* short/long mismatch */
        } else {data[0]=0xa0;data[1]=4;}
        if(mode==2) {data[0]=5;data[1]=250;if(len==16) {data[4]=4;data[5]=0x38;data[6]=9;data[7]=0x24;}}
        if(mode==3) {data[0]=5;data[1]=250;if(len==16) {data[4]=4;data[5]=0x38;data[6]=9;data[7]=0x25;}}
        if(mode==4) {data[0]=5;data[1]=249;}
        return 0;
    }
    assert(offset==0x9a && len==2 && phase==5 && page==LT_EVENT+0x9a);
    phase=6;data[0]=mode==2 ? 0x41 : 0x40;data[1]=0x59;return 0;
}
static void lt_wait(unsigned ms) {assert(ms==100 && phase==0 && page==LT_EVENT);waits++;}
/* HELPER */
int main(void) {
    for(mode=0;mode<7;mode++) {
        tries=waits=phase=calls=0;
        bool result=lt_identify();
        if(mode==0) assert(result && tries==2 && waits==1);
        else if(mode==1) assert(result && tries==3 && waits==2);
        else if(mode==5) assert(!result && tries==1 && waits==0 && calls==1);
        else assert(!result && tries==20 && waits==19);
        assert(page==LT_EVENT);
    }
    puts("PASS: transient startup, short/long consistency, wrong PID/geometry/complement, bounded rejection, transport fail stops, event page restored");
}
'''.replace('/* HELPER */',helper)
with tempfile.TemporaryDirectory() as folder:
    c,binary=Path(folder)/'ready.c',Path(folder)/'ready'
    c.write_text(program)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(binary)],check=True)
    result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
    print(result.stdout.splitlines()[-1])
