"""Exercise the real UFS command guard and GPT parser with bounded mock reads."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
args = parser.parse_args()
text = (args.xnu / 'bsd/dev/sweet_ufs.c').read_text()
begin = text.index('static int\nufs_find_partition(')
gpt = text[begin:text.index('\n}\n', begin) + 3]
begin = text.index('#if defined(LEMON_4K)', text.index('ufs_scsi(const uint8_t'))
guard = text[begin:text.index('#endif', begin)] + '#endif\n'
begin = text.index('static int\nufs_write_blocks(')
writer = text[begin:text.index('\n}\n', begin) + 3]
begin = text.index('\t/* Pin this phone\'s verified userdata extent')
extent = text[begin:text.index('\tprintf("LEMON UFS READ:', begin)]
rw_assignment = next(line for line in text.splitlines() if 'su.writable = lemon_ufs_root' in line)
test = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define LEMON_4K 1
#define BOUNCE_SIZE (1u << 20)
#define UFS_BLOCK 4096u
#define DMA_BOUNCE 0
/* Darwin uint64_t uses a different printf type from Linux; logging is mocked. */
static int quiet_printf(const char *format, ...) { (void)format; return 0; }
#define printf quiet_printf
static uint8_t dma[BOUNCE_SIZE], header[UFS_BLOCK], entries[16384];
static struct { uintptr_t dma; unsigned lun; uint64_t first_block, nblocks; bool writable; } su;
static bool lemon_ufs_root;
static int reads, fail_read;
static int ufs_read_blocks(uint64_t lba, uint32_t count) {
    assert(count && count <= BOUNCE_SIZE/UFS_BLOCK);
    reads++;
    if (fail_read) return EIO;
    if (lba==1 && count==1) memcpy(dma,header,sizeof(header));
    else { assert(lba==2 && count==4); memcpy(dma,entries,sizeof(entries)); }
    return 0;
}
/* ACTUAL_GPT */
static int command(const uint8_t *cdb, unsigned cdb_len, bool write) {
/* ACTUAL_GUARD */
    return 0;
}
static unsigned commands;
static int ufs_scsi(const uint8_t *cdb, unsigned cdb_len, uint32_t length, bool write) {
    int error=command(cdb,cdb_len,write);
    if (error) return error;
    assert(cdb_len==10 && cdb[0]==0x2a && write);
    unsigned blocks=((unsigned)cdb[7]<<8)|cdb[8];
    assert(length==blocks*UFS_BLOCK);
    commands++;
    return 0;
}
/* ACTUAL_WRITER */
static int validate_extent(void) {
    int error=0;
/* ACTUAL_EXTENT */
    return error;
}
static void configure_writes(unsigned rw) {
/* ACTUAL_RW_ASSIGNMENT */
}
static void put32(uint8_t *p, uint32_t n) { memcpy(p,&n,4); }
static void put64(uint8_t *p, uint64_t n) { memcpy(p,&n,8); }
int main(void) {
    su.dma=(uintptr_t)dma;
    memcpy(header,"EFI PART",8);
    put64(header+72,2); put32(header+80,128); put32(header+84,128);
    put64(entries+32,0x20d918); put64(entries+40,0x20d918+12347107-1);
    const char *name="userdata";
    for (unsigned i=0; name[i]; i++) entries[56+2*i]=name[i];
    assert(ufs_find_partition("userdata")==0);
    assert(su.first_block==0x20d918 && su.nblocks==12347107 && reads==2);
    assert(ufs_find_partition("missing")==ENOENT);
    put64(entries+40,0); assert(ufs_find_partition("userdata")==ENXIO);
    put32(header+80,0x20000000); reads=0;
    assert(ufs_find_partition("userdata")==ENXIO && reads==1);
    put32(header+80,0); assert(ufs_find_partition("userdata")==ENXIO);
    fail_read=1; assert(ufs_find_partition("userdata")==EIO);
    for (unsigned opcode=0; opcode<256; opcode++) {
        uint8_t cdb[10]={(uint8_t)opcode};
        assert(command(cdb,10,false)==((opcode==0 || opcode==0x28) ? 0 : EROFS));
        assert(command(cdb,10,true)==EROFS);
        assert(command(cdb,0,false)==EROFS);
    }
    lemon_ufs_root=true;
    for (unsigned writable=0; writable<2; writable++) {
        su.writable=writable;
        for (unsigned opcode=0; opcode<256; opcode++) {
            uint8_t cdb[10]={(uint8_t)opcode};
            bool read=opcode==0 || opcode==0x28 || (writable && opcode==0x35);
            bool write=writable && opcode==0x2a;
            assert(command(cdb,10,false)==(read ? 0 : EROFS));
            assert(command(cdb,10,true)==(write ? 0 : EROFS));
        }
    }
    su.first_block=0x20d918; su.nblocks=12347107;
    assert(validate_extent()==0);
    su.lun=1; assert(validate_extent()==ENXIO); su.lun=0;
    su.first_block++; assert(validate_extent()==ENXIO); su.first_block--;
    su.nblocks--; assert(validate_extent()==ENXIO); su.nblocks++;
    assert(ufs_write_blocks(su.first_block,1)==0);
    assert(ufs_write_blocks(su.first_block+su.nblocks-1,1)==0);
    assert(commands==2);
    assert(ufs_write_blocks(su.first_block-1,1)==EPERM);
    assert(ufs_write_blocks(su.first_block+su.nblocks,1)==EPERM);
    assert(ufs_write_blocks(su.first_block+su.nblocks-1,2)==EPERM);
    assert(ufs_write_blocks(su.first_block,0)==EPERM);
    assert(ufs_write_blocks(su.first_block,BOUNCE_SIZE/UFS_BLOCK+1)==EPERM);
    assert(ufs_write_blocks(UINT64_MAX,2)==EPERM);
    su.writable=false; assert(ufs_write_blocks(su.first_block,1)==EPERM);
    assert(commands==2);
    for (unsigned root=0; root<2; root++) {
        lemon_ufs_root=root;
        for (unsigned rw=0; rw<3; rw++) {
            configure_writes(rw);
            assert(su.writable==(root && rw==1));
        }
    }
    puts("PASS: GPT parser,256 opcodes in diagnostic/RO/RW modes,pinned geometry,write bounds");
}
'''.replace('/* ACTUAL_GPT */', gpt).replace('/* ACTUAL_GUARD */', guard).replace(
    '/* ACTUAL_WRITER */', writer).replace('/* ACTUAL_EXTENT */', extent).replace(
    '/* ACTUAL_RW_ASSIGNMENT */', rw_assignment)
with tempfile.TemporaryDirectory() as folder:
    source, binary = Path(folder) / 'read.c', Path(folder) / 'read'
    source.write_text(test)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
