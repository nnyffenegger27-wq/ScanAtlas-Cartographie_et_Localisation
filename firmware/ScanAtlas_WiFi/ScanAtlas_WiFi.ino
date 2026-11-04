/* ScanAtlas : ESP32 classique, Arduino-ESP32 2.0.17, Keyestudio Mecanum V2.
 * Le firmware de démonstration original reste inchangé dans materiel/MecanumCarV2/.
 * Démarrage à l'arrêt. Un seul pilote. Les commandes n'ont pas d'odométrie.
 */
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_timer.h>
#include <freertos/semphr.h>
#include <esp_system.h>
#include <stdarg.h>
#include "motor_driver.h"
#include "protocol.h"
#include "usb_live.h"

const char *AP_SSID="ScanAtlas";
const char *AP_PASSWORD="ScanAtlas2026"; // Modifier ici avant flash si souhaité.
const uint16_t COMMAND_PORT=4210,SCAN_PORT=4211;
MotorDriver car;  // PWM ou I2C : choix et profil dans motor_config.h.
WiFiUDP udp;
WiFiServer server(SCAN_PORT);
QueueHandle_t scans,scansUSB;
unsigned usbRemaining=0;
SemaphoreHandle_t ownerMutex;
char ownerToken[33]={0};IPAddress ownerIP;bool ownerActive=false;
uint32_t dataAlive=0;  // millis du dernier tour transféré (pas de backlog moteur).

// Journal d'événements sur la console série, pour comprendre une coupure (redémarrage, bail, client).
// Suspendu pendant la liaison filaire et les captures CSV, où la console porte des données.
const bool LOG_LIAISON=true;
UsbLive live;                        // liaison filaire : modifiée par loop() seulement
bool liveActive=false;               // copie protégée par ownerMutex, lue par commandTask
Motion liveApplied=STOP;Command liveCurrent={};
void logLiaison(const char *fmt,...){
  if(!LOG_LIAISON||liveActive||usbRemaining>0)return;
  char line[120];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
  Serial.printf("[%lu ms] %s\n",(unsigned long)millis(),line);
}
const char *resetName(){
  switch(esp_reset_reason()){
    case ESP_RST_POWERON:return "mise sous tension";
    case ESP_RST_EXT:return "broche reset";
    case ESP_RST_SW:return "redemarrage logiciel";
    case ESP_RST_PANIC:return "PLANTAGE du programme";
    case ESP_RST_INT_WDT:case ESP_RST_TASK_WDT:case ESP_RST_WDT:return "watchdog (programme bloque)";
    case ESP_RST_BROWNOUT:return "BROWNOUT (tension trop basse : alimentation / batterie)";
    case ESP_RST_DEEPSLEEP:return "sortie de veille";
    default:return "autre";
  }
}
void applyCommand(const Command &c) {
  if(c.motion==DRIVE)car.drive(c.vx,c.vy,c.w);
  else car.apply(c.motion,c.pwm);
}
void reply(const char *s,IPAddress ip,uint16_t port){
  udp.beginPacket(ip,port);udp.write((const uint8_t*)s,strlen(s));udp.endPacket();
}

void commandTask(void *) {
  Lease lease;uint16_t ownerPort=0;Motion applied=STOP;Command current={};
  for(;;){
    uint32_t now=millis();
    if(lease.expired(now)&&!lease.lapsed){
      logLiaison("Wi-Fi : plus de commande depuis 300 ms, moteurs coupes (session gardee 6 s).");
      car.stop();applied=STOP;current=Command{};lease.lapsed=true;
    }
    if(lease.dead(now)){
      logLiaison("Session Wi-Fi fermee : plus de commande depuis 6 s.");
      lease.close();car.stop();applied=STOP;current=Command{};
      xSemaphoreTake(ownerMutex,portMAX_DELAY);ownerActive=false;xSemaphoreGive(ownerMutex);
    }
    // Si le PC ne reçoit plus les scans, on n'entretient pas un mouvement aveugle.
    xSemaphoreTake(ownerMutex,portMAX_DELAY);bool fresh=usbRemaining==0&&dataAlive!=0&&uint32_t(millis()-dataAlive)<600;xSemaphoreGive(ownerMutex);
    if(!fresh&&applied!=STOP){car.stop();applied=STOP;current=Command{};}
    int n=udp.parsePacket();
    if(n>0){
      char buf[128];int got=udp.read(buf,sizeof(buf)-1);buf[got>0?got:0]=0;
      IPAddress ip=udp.remoteIP();uint16_t port=udp.remotePort();
      if(n>=int(sizeof(buf))){vTaskDelay(pdMS_TO_TICKS(2));continue;}
      char tok[33],extra;
      if(sscanf(buf,"HELLO %32s %c",tok,&extra)==1&&tokenValid(tok)){
        bool blocked=false;
        // Une session muette depuis plus d'une seconde (PC planté, câble ou Wi-Fi coupé) cède la place
        // à une nouvelle demande : on n'attend plus la fin des 6 s pour se reconnecter.
        if(lease.silent(now)&&!(ip==ownerIP&&port==ownerPort&&!strcmp(tok,ownerToken))){
          logLiaison("Session Wi-Fi remplacee par une nouvelle demande.");
          lease.close();car.stop();applied=STOP;current=Command{};
          xSemaphoreTake(ownerMutex,portMAX_DELAY);ownerActive=false;xSemaphoreGive(ownerMutex);
        }
        if(!lease.active){
          xSemaphoreTake(ownerMutex,portMAX_DELAY);blocked=liveActive;xSemaphoreGive(ownerMutex);
          if(!blocked){
            car.stop();applied=STOP;current=Command{};lease.open(now);ownerPort=port;
            xSemaphoreTake(ownerMutex,portMAX_DELAY);
            strcpy(ownerToken,tok);ownerIP=ip;ownerActive=true;dataAlive=0;
            xSemaphoreGive(ownerMutex);
            logLiaison("Session Wi-Fi ouverte.");
          }
        }
        if(blocked)reply("BUSY\n",ip,port);
        else if(ip==ownerIP&&port==ownerPort&&!strcmp(tok,ownerToken)){
          // « SA2 » annonce la commande combinée ; un ancien firmware répond « READY jeton » seul.
          char out[56];snprintf(out,sizeof(out),"READY %s SA2\n",tok);reply(out,ip,port);
        }else reply("BUSY\n",ip,port);
      }else{
        Command cmd;
        if(parseCommand(buf,cmd)&&ip==ownerIP&&port==ownerPort&&!strcmp(cmd.token,ownerToken)&&lease.accept(cmd,now)){
          Command effective=cmd;
          if(!fresh||lease.resumed){effective.motion=STOP;effective.vx=effective.vy=effective.w=0;}
          if(!sameDrive(effective,current)){applyCommand(effective);applied=effective.motion;current=effective;}
          char out[96];snprintf(out,sizeof(out),"SA1 %s %lu %s\n",ownerToken,(unsigned long)cmd.seq,MOTIONS[effective.motion]);reply(out,ip,port);
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

void scanTask(void *) {
  static ScanFrame frame;
  for(;;){
    WiFiClient client=server.available();
    if(!client){vTaskDelay(pdMS_TO_TICKS(10));continue;}
    client.setNoDelay(true);client.setTimeout(200);
    char token[34]={0};size_t n=0;uint32_t start=millis();
    while(client.connected()&&millis()-start<1000&&n<33){
      if(client.available()){char c=client.read();if(c=='\n')break;token[n++]=c;}
      else vTaskDelay(pdMS_TO_TICKS(2));
    }
    token[n]=0;
    xSemaphoreTake(ownerMutex,portMAX_DELAY);
    bool allowed=ownerActive&&client.remoteIP()==ownerIP&&tokenValid(token)&&!strcmp(token,ownerToken);
    xSemaphoreGive(ownerMutex);
    if(!allowed){client.stop();continue;}
    xQueueReset(scans); // Les données en attente avant la connexion ne sont pas transmises.
    logLiaison("Flux de scans Wi-Fi ouvert.");
    while(client.connected()){
      xSemaphoreTake(ownerMutex,portMAX_DELAY);
      allowed=ownerActive&&!strcmp(token,ownerToken);xSemaphoreGive(ownerMutex);
      if(!allowed)break;
      if(xQueueReceive(scans,&frame,pdMS_TO_TICKS(100))!=pdTRUE)continue;
      size_t offset=0;start=millis();
      while(offset<frame.size&&client.connected()&&millis()-start<2000){  // un trou Wi-Fi de 300 ms ne ferme plus le flux
        // Envoi borné par socket ; tâche séparée du watchdog et de l'UART.
        size_t sent=client.write(frame.bytes+offset,frame.size-offset);
        if(!sent)break;offset+=sent;
      }
      if(offset!=frame.size)break;
      xSemaphoreTake(ownerMutex,portMAX_DELAY);dataAlive=millis();xSemaphoreGive(ownerMutex);
    }
    client.stop();
    logLiaison("Flux de scans Wi-Fi ferme.");
    xSemaphoreTake(ownerMutex,portMAX_DELAY);dataAlive=0;xSemaphoreGive(ownerMutex);
  }
}

void usbTask(void *) {
  static ScanFrame frame;
  for(;;){
    if(xQueueReceive(scansUSB,&frame,pdMS_TO_TICKS(100))!=pdTRUE)continue;
    xSemaphoreTake(ownerMutex,portMAX_DELAY);bool active=usbRemaining>0;xSemaphoreGive(ownerMutex);
    if(!active)continue;
    uint16_t n=uint16_t(frame.bytes[6])|(uint16_t(frame.bytes[7])<<8);
    Serial.println("N,Angle_deg,Distance_mm,Intensity,X_mm,Y_mm");
    for(unsigned i=0;i<n;++i){
      xSemaphoreTake(ownerMutex,portMAX_DELAY);active=usbRemaining>0;xSemaphoreGive(ownerMutex);
      if(!active)break;
      const uint8_t *p=frame.bytes+26+i*5;
      double angle=(uint16_t(p[0])|(uint16_t(p[1])<<8))*.01;
      unsigned distance=uint16_t(p[2])|(uint16_t(p[3])<<8);
      double a=angle*3.141592653589793/180.;
      Serial.printf("%u,%.2f,%u,%u,%.2f,%.2f\n",i,angle,distance,unsigned(p[4]),distance*cos(a),distance*sin(a));
    }
    Serial.println();
    xSemaphoreTake(ownerMutex,portMAX_DELAY);if(usbRemaining)--usbRemaining;xSemaphoreGive(ownerMutex);
  }
}

void setup(){
  Serial.begin(115200);
  Serial.printf("\nDemarrage ScanAtlas. Cause du dernier redemarrage : %s\n",resetName());
  if(!car.begin()){Serial.print("Profil moteur invalide (pilote ");Serial.print(MotorDriver::name());Serial.println(") : verifier motor_config.h");while(true)delay(1000);}
  Serial.print("Pilote moteur : ");Serial.println(MotorDriver::name());
  car.stop();
  if(MOTOR_DIAGNOSTIC){Serial.println("Test moteurs : 1..4 un sens ; a..d l'autre sens ; espace STOP. Impulsions 250 ms / puissance 50.");return;}
  pinMode(32,OUTPUT);digitalWrite(32,HIGH);
  Serial2.setRxBufferSize(8192);Serial2.begin(230400,SERIAL_8N1,33,-1);
  ownerMutex=xSemaphoreCreateMutex();scans=xQueueCreate(1,sizeof(ScanFrame));scansUSB=xQueueCreate(1,sizeof(ScanFrame));
  if(!ownerMutex||!scans||!scansUSB){Serial.println("Allocation impossible : moteurs arretes.");while(true)delay(1000);}
  WiFi.mode(WIFI_AP);WiFi.setSleep(false);
  if(!WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0))||
     !WiFi.softAP(AP_SSID,AP_PASSWORD,6,0,1)){
    Serial.println("Point acces impossible : moteurs arretes.");while(true)delay(1000);
  }
  WiFi.onEvent([](WiFiEvent_t event,WiFiEventInfo_t info){
    const uint8_t *m=info.wifi_ap_staconnected.mac;
    logLiaison("Wi-Fi : appareil associe (%02x:%02x:%02x:%02x:%02x:%02x).",m[0],m[1],m[2],m[3],m[4],m[5]);
  },ARDUINO_EVENT_WIFI_AP_STACONNECTED);
  WiFi.onEvent([](WiFiEvent_t event,WiFiEventInfo_t info){
    const uint8_t *m=info.wifi_ap_stadisconnected.mac;
    logLiaison("Wi-Fi : appareil DECONNECTE (%02x:%02x:%02x:%02x:%02x:%02x).",m[0],m[1],m[2],m[3],m[4],m[5]);
  },ARDUINO_EVENT_WIFI_AP_STADISCONNECTED);
  udp.begin(COMMAND_PORT);server.begin();
  if(xTaskCreate(commandTask,"commands",6144,nullptr,3,nullptr)!=pdPASS||
     xTaskCreate(scanTask,"scans",6144,nullptr,1,nullptr)!=pdPASS||
     xTaskCreate(usbTask,"usb",4096,nullptr,1,nullptr)!=pdPASS){
    car.stop();Serial.println("Taches impossibles.");while(true)delay(1000);
  }
  Serial.print("ScanAtlas AP : ");Serial.println(WiFi.softAPIP());
}
// Débit réellement réglé sur la console (le PC doit parler au même débit).
static unsigned serialBaud=115200;
void setSerialBaud(unsigned baud){
  if(baud==serialBaud)return;
  Serial.flush();delay(20);Serial.updateBaudRate(baud);serialBaud=baud;
}
// Ferme la liaison filaire : arrêt moteurs et retour au débit historique.
void liveClose(const char *why){
  xSemaphoreTake(ownerMutex,portMAX_DELAY);liveActive=false;xSemaphoreGive(ownerMutex);
  car.stop();liveApplied=STOP;liveCurrent=Command{};
  live.close();
  setSerialBaud(115200);
  logLiaison("Liaison filaire fermee : %s.",why);
}
void liveCommand(const Command &cmd,uint32_t now){
  if(!live.owns(cmd.token)||!live.lease.accept(cmd,now))return;
  Command effective=cmd;
  if(!live.fresh(now)||live.lease.resumed){effective.motion=STOP;effective.vx=effective.vy=effective.w=0;}
  if(!sameDrive(effective,liveCurrent)){applyCommand(effective);liveApplied=effective.motion;liveCurrent=effective;}
  Serial.printf("SA1 %s %lu %s\n",live.token,(unsigned long)cmd.seq,MOTIONS[effective.motion]);
}
// Une ligne reçue sur la console : session filaire, commande, ou requête CSV historique.
void handleLine(const char *line,uint32_t now){
  LiveRequest request;Command cmd;unsigned count;
  if(parseLive(line,request)){
    xSemaphoreTake(ownerMutex,portMAX_DELAY);
    // Une session filaire muette depuis plus d'une seconde (PC replanté, câble débranché) est remplacée
    // par la nouvelle demande, sans attendre les 6 s de fermeture et sans repasser à 115200.
    if(live.active&&strcmp(live.token,request.token)&&live.lease.silent(now)){live.close();liveActive=false;}
    UsbLive::Open result=ownerActive?UsbLive::REFUSED:live.open(request,now);
    if(result==UsbLive::OPENED){liveActive=true;usbRemaining=0;xQueueReset(scansUSB);}
    xSemaphoreGive(ownerMutex);
    if(result==UsbLive::REFUSED){Serial.println("BUSY");return;}
    if(result==UsbLive::OPENED){car.stop();liveApplied=STOP;liveCurrent=Command{};}
    Serial.printf("READY %s SA2\n",request.token);
    setSerialBaud(request.baud);
    return;
  }
  if(isLiveStop(line)){if(live.active)liveClose("arret demande par le PC");return;}
  if(live.active){if(parseCommand(line,cmd))liveCommand(cmd,now);return;}
  if(parseUsbRequest(line,count)){
    xSemaphoreTake(ownerMutex,portMAX_DELAY);
    if(!ownerActive||count==0){usbRemaining=count;xQueueReset(scansUSB);}
    else Serial.println("BUSY : deconnecter le pilotage Wi-Fi avant USB");
    xSemaphoreGive(ownerMutex);
  }
}
void loop(){
  if(MOTOR_DIAGNOSTIC){
    static uint32_t deadline=0;
    while(Serial.available()){
      char c=Serial.read();int motor=-1,power=50;
      if(c>='1'&&c<='4')motor=c-'1';
      if(c>='a'&&c<='d'){motor=c-'a';power=-50;}
      if(motor>=0){car.stop();car.wheel(motor,power);deadline=millis()+250;}
      else if(c==' '){car.stop();deadline=0;}
    }
    if(deadline&&int32_t(millis()-deadline)>=0){car.stop();deadline=0;}
    delay(1);return;
  }
  static LidarParser parser;static ScanFrame frame;
  static char request[96];static unsigned length=0;static bool overflow=false;
  for(int n=0;n<64&&Serial.available();++n){
    char c=Serial.read();
    if(c=='\n'){
      request[length]=0;
      if(!overflow)handleLine(request,millis());
      length=0;overflow=false;
    }else if(c!='\r'){
      if(length<sizeof(request)-1)request[length++]=c;else overflow=true;
    }
  }
  if(live.active){
    uint32_t now=millis();
    if(live.lease.dead(now))liveClose("plus de commande depuis 6 s");
    else if(live.lease.expired(now)&&!live.lease.lapsed){
      // Trou de commandes : moteurs coupés tout de suite, session gardée (le flux de scans continue).
      car.stop();liveApplied=STOP;liveCurrent=Command{};live.lease.lapsed=true;
      logLiaison("Liaison filaire : plus de commande depuis 300 ms, moteurs coupes (session gardee 6 s).");
    }
    else if(!live.fresh(now)&&liveApplied!=STOP){car.stop();liveApplied=STOP;liveCurrent=Command{};}
  }
  // Un tour par trame, CRC UART puis CRC réseau. La file ne garde que le dernier.
  static uint32_t lastByte=0,lastTurn=0;static bool lidarSilent=false;
  for(int n=0;n<4096&&Serial2.available();++n){
    uint8_t b=Serial2.read();lastByte=millis();
    if(parser.feed(b,esp_timer_get_time(),frame)){
      lastTurn=millis();
      if(lidarSilent){lidarSilent=false;logLiaison("Lidar : tours de nouveau recus.");}
      xQueueOverwrite(scans,&frame);
      xSemaphoreTake(ownerMutex,portMAX_DELAY);bool wanted=usbRemaining>0;xSemaphoreGive(ownerMutex);
      if(wanted)xQueueOverwrite(scansUSB,&frame);
      if(live.active){Serial.write(frame.bytes,frame.size);live.lastFrame=millis();}  // liaison filaire
    }
  }
  // Lidar muet : câblage ou alimentation du capteur plutôt que Wi-Fi.
  if(!lidarSilent&&millis()>4000&&uint32_t(millis()-(lastTurn?lastTurn:4000))>1500){
    lidarSilent=true;
    logLiaison(lastByte?"Lidar : plus de tour complet depuis 1,5 s.":"Lidar : AUCUN octet recu (alimentation, cable ou broche 33).");
  }
  delay(1);
}

