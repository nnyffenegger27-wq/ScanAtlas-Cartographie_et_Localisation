/* ScanAtlas : ESP32 classique, Arduino-ESP32 2.0.17, Keyestudio Mecanum V2.
 * Le firmware de démonstration original reste inchangé dans MecanumCarV2/.
 * Démarrage à l'arrêt. Un seul pilote. Les commandes n'ont pas d'odométrie.
 */
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_timer.h>
#include <freertos/semphr.h>
#include "motor_pwm.h"
#include "protocol.h"

const char *AP_SSID="ScanAtlas";
const char *AP_PASSWORD="ScanAtlas2026"; // Modifier ici avant flash si souhaité.
const uint16_t COMMAND_PORT=4210,SCAN_PORT=4211;
MotorPWM car;  // PWM direct ; profil dans motor_config.h.
WiFiUDP udp;
WiFiServer server(SCAN_PORT);
QueueHandle_t scans,scansUSB;
unsigned usbRemaining=0;
SemaphoreHandle_t ownerMutex;
char ownerToken[33]={0};IPAddress ownerIP;bool ownerActive=false;
uint32_t dataAlive=0;  // millis du dernier tour transféré (pas de backlog moteur).

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
    if(lease.expired(now)){
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
        if(!lease.active){
          car.stop();applied=STOP;current=Command{};lease.open(now);ownerPort=port;
          xSemaphoreTake(ownerMutex,portMAX_DELAY);
          strcpy(ownerToken,tok);ownerIP=ip;ownerActive=true;dataAlive=0;
          xSemaphoreGive(ownerMutex);
        }
        if(ip==ownerIP&&port==ownerPort&&!strcmp(tok,ownerToken)){
          // « SA2 » annonce la commande combinée ; un ancien firmware répond « READY jeton » seul.
          char out[56];snprintf(out,sizeof(out),"READY %s SA2\n",tok);reply(out,ip,port);
        }else reply("BUSY\n",ip,port);
      }else{
        Command cmd;
        if(parseCommand(buf,cmd)&&ip==ownerIP&&port==ownerPort&&!strcmp(cmd.token,ownerToken)&&lease.accept(cmd,now)){
          Command effective=cmd;
          if(!fresh){effective.motion=STOP;effective.vx=effective.vy=effective.w=0;}
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
    while(client.connected()){
      xSemaphoreTake(ownerMutex,portMAX_DELAY);
      allowed=ownerActive&&!strcmp(token,ownerToken);xSemaphoreGive(ownerMutex);
      if(!allowed)break;
      if(xQueueReceive(scans,&frame,pdMS_TO_TICKS(100))!=pdTRUE)continue;
      size_t offset=0;start=millis();
      while(offset<frame.size&&client.connected()&&millis()-start<300){
        // Envoi borné par socket ; tâche séparée du watchdog et de l'UART.
        size_t sent=client.write(frame.bytes+offset,frame.size-offset);
        if(!sent)break;offset+=sent;
      }
      if(offset!=frame.size)break;
      xSemaphoreTake(ownerMutex,portMAX_DELAY);dataAlive=millis();xSemaphoreGive(ownerMutex);
    }
    client.stop();
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
  if(!car.begin()){Serial.println("Profil PWM invalide : verifier motor_config.h");while(true)delay(1000);}
  car.stop();
  if(MOTOR_DIAGNOSTIC){Serial.println("Test PWM : 1..4 sens A ; a..d sens B ; espace STOP. Impulsions 250 ms / PWM 50.");return;}
  pinMode(32,OUTPUT);digitalWrite(32,HIGH);
  Serial2.setRxBufferSize(8192);Serial2.begin(230400,SERIAL_8N1,33,-1);
  ownerMutex=xSemaphoreCreateMutex();scans=xQueueCreate(1,sizeof(ScanFrame));scansUSB=xQueueCreate(1,sizeof(ScanFrame));
  if(!ownerMutex||!scans||!scansUSB){Serial.println("Allocation impossible : moteurs arretes.");while(true)delay(1000);}
  WiFi.mode(WIFI_AP);WiFi.setSleep(false);
  if(!WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0))||
     !WiFi.softAP(AP_SSID,AP_PASSWORD,6,0,1)){
    Serial.println("Point acces impossible : moteurs arretes.");while(true)delay(1000);
  }
  udp.begin(COMMAND_PORT);server.begin();
  if(xTaskCreate(commandTask,"commands",6144,nullptr,3,nullptr)!=pdPASS||
     xTaskCreate(scanTask,"scans",6144,nullptr,1,nullptr)!=pdPASS||
     xTaskCreate(usbTask,"usb",4096,nullptr,1,nullptr)!=pdPASS){
    car.stop();Serial.println("Taches impossibles.");while(true)delay(1000);
  }
  Serial.print("ScanAtlas AP : ");Serial.println(WiFi.softAPIP());
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
  static char request[32];static unsigned length=0;static bool overflow=false;
  for(int n=0;n<64&&Serial.available();++n){
    char c=Serial.read();
    if(c=='\n'){
      request[length]=0;unsigned count;
      if(!overflow&&parseUsbRequest(request,count)){
        xSemaphoreTake(ownerMutex,portMAX_DELAY);
        if(!ownerActive||count==0){usbRemaining=count;xQueueReset(scansUSB);}
        else Serial.println("BUSY : deconnecter le pilotage Wi-Fi avant USB");
        xSemaphoreGive(ownerMutex);
      }
      length=0;overflow=false;
    }else if(c!='\r'){
      if(length<sizeof(request)-1)request[length++]=c;else overflow=true;
    }
  }
  // Un tour par trame, CRC UART puis CRC réseau. La file ne garde que le dernier.
  for(int n=0;n<4096&&Serial2.available();++n)
    if(parser.feed(Serial2.read(),esp_timer_get_time(),frame)){
      xQueueOverwrite(scans,&frame);
      xSemaphoreTake(ownerMutex,portMAX_DELAY);bool wanted=usbRemaining>0;xSemaphoreGive(ownerMutex);
      if(wanted)xQueueOverwrite(scansUSB,&frame);
    }
  delay(1);
}

