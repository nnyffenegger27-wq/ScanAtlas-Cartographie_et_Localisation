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
enum Motion { STOP, FORWARD, BACK, LEFT, RIGHT, STRAFE_L, STRAFE_R, DRIVE };
static const char *const MOTIONS[]={"STOP","FORWARD","BACK","LEFT","RIGHT","STRAFE_L","STRAFE_R","DRIVE"};
inline bool tokenValid(const char *s) {
  if(strlen(s)!=32)return false;
  for(int i=0;i<32;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;
  return true;
}
// vx : avance (+) / recule (-) ; vy : gauche (+) / droite (-) ; w : rotation
// à gauche (+) / à droite (-). Pourcentages de -100 à 100, même échelle que pwm.
struct Command { char token[33];uint32_t seq;Motion motion;unsigned pwm;int vx,vy,w; };
inline int absInt(int v){return v<0?-v:v;}
inline int max3(int a,int b,int c){return a>b?(a>c?a:c):(b>c?b:c);}
inline bool sameDrive(const Command &a,const Command &b){
  return a.motion==b.motion&&a.pwm==b.pwm&&a.vx==b.vx&&a.vy==b.vy&&a.w==b.w;
}
// Mixage mécanum en X, ordre des roues : avant gauche, avant droite, arrière
// gauche, arrière droite. Si une roue dépasse 100, tout est réduit ensemble :
// la direction demandée est conservée, seule la vitesse diminue.
inline void mecanumMix(int vx,int vy,int w,int out[4]){
  int m[4]={vx-vy-w,vx+vy+w,vx+vy-w,vx-vy+w};
  int peak=0;
  for(int i=0;i<4;++i)if(absInt(m[i])>peak)peak=absInt(m[i]);
  for(int i=0;i<4;++i)out[i]=peak>100?m[i]*100/peak:m[i];
}
inline bool parseCommand(const char *s,Command &c) {
  char cmd[16],extra;unsigned long long seq;unsigned pwm;int vx,vy,w;
  c.vx=c.vy=c.w=0;
  if(!strncmp(s,"SA2 ",4)){
    // Commande combinée : SA2 jeton séquence vx vy w
    if(sscanf(s,"SA2 %32s %llu %d %d %d %c",c.token,&seq,&vx,&vy,&w,&extra)!=5 ||
       !tokenValid(c.token)||seq>0xffffffffull||!seq||
       absInt(vx)>100||absInt(vy)>100||absInt(w)>100)return false;
    c.seq=(uint32_t)seq;c.vx=vx;c.vy=vy;c.w=w;
    c.pwm=(unsigned)max3(absInt(vx),absInt(vy),absInt(w));
    c.motion=c.pwm?DRIVE:STOP;return true;
  }
  if(sscanf(s,"SA1 %32s %llu %15s %u %c",c.token,&seq,cmd,&pwm,&extra)!=4 ||
     !tokenValid(c.token)||seq>0xffffffffull||!seq||pwm>100)return false;
  for(int i=0;i<7;++i)if(!strcmp(cmd,MOTIONS[i])) {
    c.seq=(uint32_t)seq;c.motion=(Motion)i;c.pwm=pwm;return true;
  }
  return false;
}
// Deux délais distincts. Sans commande depuis 300 ms, les MOTEURS sont coupés (sécurité, « expired »).
// La SESSION (propriétaire, flux de scans) ne se ferme qu'après 6 s de silence (« dead ») : un trou de
// quelques centaines de ms du Wi-Fi ou du PC ne doit plus couper tout le flux (c'était la cause des
// reconnexions incessantes). Au retour des commandes après une coupure des moteurs, la première
// commande est acceptée mais appliquée comme STOP (« resumed »), la suivante agit normalement.
struct Lease {
  static const uint32_t MOTOR_MS=300,SESSION_MS=6000,TAKEOVER_MS=1000;
  bool active=false,primed=false,lapsed=false,resumed=false;uint32_t last=0,seq=0;Motion motion=STOP;
  void open(uint32_t now) {active=true;primed=false;lapsed=false;resumed=false;last=now;seq=0;motion=STOP;}
  bool expired(uint32_t now) const {return active && (uint32_t)(now-last)>MOTOR_MS;}
  bool dead(uint32_t now) const {return active && (uint32_t)(now-last)>SESSION_MS;}
  bool silent(uint32_t now) const {return active && (uint32_t)(now-last)>TAKEOVER_MS;}  // une autre session peut la remplacer
  void close(){active=false;primed=false;lapsed=false;resumed=false;motion=STOP;}
  bool accept(const Command &c,uint32_t now) {
    if(!active||dead(now)||c.seq<=seq||(!primed&&c.motion!=STOP))return false;
    resumed=expired(now);
    seq=c.seq;last=now;motion=c.motion;primed=true;lapsed=false;return true;
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
