#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

// Format explicite little endian, indépendant de l'alignement des structures.
inline void put16(uint8_t *p, uint16_t v) { p[0]=v; p[1]=v>>8; }
inline void put32(uint8_t *p, uint32_t v) { for(int i=0;i<4;++i)p[i]=v>>(8*i); }
inline void put64(uint8_t *p, uint64_t v) { for(int i=0;i<8;++i)p[i]=v>>(8*i); }
inline uint32_t crc32sa(const uint8_t *p,size_t n) {
  uint32_t c=0xffffffff;
  while(n--) { c^=*p++;for(int i=0;i<8;++i)c=(c>>1)^(0xedb88320u&(-(int32_t)(c&1))); }
  return ~c;
}
enum Motion { STOP, FORWARD, BACK, LEFT, RIGHT, STRAFE_L, STRAFE_R };
static const char *const MOTIONS[]={"STOP","FORWARD","BACK","LEFT","RIGHT","STRAFE_L","STRAFE_R"};
inline bool tokenValid(const char *s) {
  if(strlen(s)!=32)return false;
  for(int i=0;i<32;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;
  return true;
}
struct Command { char token[33];uint32_t seq;Motion motion;unsigned pwm; };
inline bool parseCommand(const char *s,Command &c) {
  char cmd[16],extra;unsigned long long seq;unsigned pwm;
  if(sscanf(s,"SA1 %32s %llu %15s %u %c",c.token,&seq,cmd,&pwm,&extra)!=4 ||
     !tokenValid(c.token)||seq>0xffffffffull||!seq||pwm>100)return false;
  for(int i=0;i<7;++i)if(!strcmp(cmd,MOTIONS[i])) {
    c.seq=(uint32_t)seq;c.motion=(Motion)i;c.pwm=pwm;return true;
  }
  return false;
}
struct Lease {
  bool active=false,primed=false;uint32_t last=0,seq=0;Motion motion=STOP;
  void open(uint32_t now) {active=true;primed=false;last=now;seq=0;motion=STOP;}
  bool expired(uint32_t now) const {return active && (uint32_t)(now-last)>300;}
  void close(){active=false;primed=false;motion=STOP;}
  bool accept(const Command &c,uint32_t now) {
    if(!active||expired(now)||c.seq<=seq||(!primed&&c.motion!=STOP))return false;
    seq=c.seq;last=now;motion=c.motion;primed=true;return true;
  }
};
struct ScanFrame {uint8_t bytes[26+1200*5+4];size_t size=0;};

// Parseur UART incrémental : pas d'attente et aucun envoi réseau ici.
// Protocole LD06, CRC8 poly 0x4d. Conversion CW -> CCW comme le code fourni.
// Origine des formats : Robot-Maker-SAS/LD06 et ESP32_LD06_Test du dépôt.
class LidarParser {
  uint8_t packet[47];int index=0,count=0;uint8_t points[1200*5];
  float lastAngle=0;bool started=false,overflow=false;uint64_t start=0;uint32_t seq=0;
 public:
  static uint8_t crc8(const uint8_t *p,size_t n) {
    uint8_t c=0;while(n--){c^=*p++;for(int i=0;i<8;++i)c=(c&0x80)?(c<<1)^0x4d:c<<1;}return c;
  }
  bool feed(uint8_t b,uint64_t now,ScanFrame &out) {
    if(index==0&&b!=0x54)return false;
    if(index==1&&b!=0x2c){index=(b==0x54)?1:0;return false;}
    packet[index++]=b;if(index<47)return false;index=0;
    if(crc8(packet,46)!=packet[46])return false;
    auto u16=[&](int i)->uint16_t{return packet[i]|(uint16_t(packet[i+1])<<8);};
    float first=u16(4)*.01f, end=u16(42)*.01f;
    float span=end-first;if(span<0)span+=360;
    if(span<=0||span>60)return false;
    bool ready=false;
    for(int i=0;i<12;++i){
      float phys=first+(i+.5f)*span/11.f;while(phys>=360)phys-=360;
      if(phys<lastAngle && lastAngle-phys>180){
        uint64_t duration=now-start;
        if(started&&!overflow&&count>0&&duration>=10000&&duration<=1000000){
          uint8_t *p=out.bytes;memcpy(p,"SA06",4);p[4]=1;p[5]=0;
          put16(p+6,count);put32(p+8,++seq);put64(p+12,now);put32(p+20,duration);put16(p+24,count*5);
          memcpy(p+26,points,count*5);out.size=26+count*5;
          put32(p+out.size,crc32sa(p,out.size));out.size+=4;ready=true;
        }
        started=true;overflow=false;count=0;start=now;
      }
      lastAngle=phys;
      if(started){
        if(count>=1200){overflow=true;continue;}
        uint16_t angle=uint16_t((360.f-phys)*100.f+.5f)%36000;
        put16(points+count*5,angle);put16(points+count*5+2,u16(6+i*3));points[count*5+4]=packet[8+i*3];++count;
      }
    }
    return ready;
  }
};


// Requête USB compatible avec le CSV historique : SCAN 0 annule.
inline bool parseUsbRequest(const char *s,unsigned &nombre){
  unsigned n;char extra;
  if(strncmp(s,"SCAN ",5)||sscanf(s+5,"%u %c",&n,&extra)!=1||n>20)return false;
  nombre=n;return true;
}
