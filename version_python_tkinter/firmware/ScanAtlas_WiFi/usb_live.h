#pragma once
#include "protocol.h"

// Liaison filaire « direct » : mêmes trames lidar SA06 et mêmes commandes SA1 / SA2 que le Wi-Fi,
// mais sur la console USB. Le PC ouvre la session au débit historique (115200) avec
//   LIVE <jeton> <débit>\n
// Le firmware répond « READY <jeton> SA2 », puis passe au débit demandé (le PC fait de même).
// Sans commande depuis 300 ms les moteurs sont coupés ; la session, elle, ne se ferme qu'après 6 s de silence
// (ou sur LIVE_STOP) : le firmware revient alors à 115200 et le mode USB historique (SCAN N) reste utilisable.
// Une nouvelle demande d'un autre jeton remplace une session muette depuis plus d'une seconde.
struct LiveRequest { char token[33]; unsigned baud; };

inline bool liveBaudAllowed(unsigned long long b){return b==115200||b==230400||b==460800||b==921600;}

inline bool parseLive(const char *s,LiveRequest &r){
  char extra;unsigned long long baud;
  if(strncmp(s,"LIVE ",5))return false;
  if(sscanf(s,"LIVE %32s %llu %c",r.token,&baud,&extra)!=2||!tokenValid(r.token)||!liveBaudAllowed(baud))return false;
  r.baud=(unsigned)baud;return true;
}
inline bool isLiveStop(const char *s){return !strcmp(s,"LIVE_STOP");}

struct UsbLive {
  enum Open { OPENED, AGAIN, REFUSED };
  bool active=false;char token[33]={0};unsigned baud=115200;Lease lease;uint32_t lastFrame=0;
  // Ouvre la session ; la même session qui redemande est annoncée de nouveau (« AGAIN »).
  Open open(const LiveRequest &r,uint32_t now){
    if(active)return strcmp(token,r.token)?REFUSED:AGAIN;
    strcpy(token,r.token);baud=r.baud;active=true;lease.open(now);lastFrame=0;return OPENED;
  }
  void close(){active=false;lease.close();token[0]=0;lastFrame=0;baud=115200;}
  bool owns(const char *t) const {return active&&!strcmp(t,token);}
  // Les commandes ne partent que si des tours lidar viennent d'être transmis (pas de mouvement aveugle).
  bool fresh(uint32_t now) const {return active&&lastFrame!=0&&(uint32_t)(now-lastFrame)<600;}
};
