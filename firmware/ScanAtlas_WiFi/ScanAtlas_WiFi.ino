/* ScanAtlas : ESP32 classique, Arduino-ESP32 2.0.17, Keyestudio Mecanum V2.
 * Le firmware de démonstration original reste inchangé dans MecanumCarV2/.
 * Démarrage à l'arrêt. Un seul pilote. Les commandes n'ont pas d'odométrie.
 */
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_timer.h>
#include <freertos/semphr.h>
#include "MecanumCar_v2.h"
#include "protocol.h"

const char *AP_SSID="ScanAtlas";
const char *AP_PASSWORD="ScanAtlas2026"; // Modifier ici avant flash si souhaité.
const uint16_t COMMAND_PORT=4210,SCAN_PORT=4211;
mecanumCar car(19,21);  // Broches du README matériel fourni, pas SDA/SCL par défaut.
WiFiUDP udp;
WiFiServer server(SCAN_PORT);
QueueHandle_t scans;
SemaphoreHandle_t ownerMutex;
char ownerToken[33]={0};IPAddress ownerIP;bool ownerActive=false;
uint32_t dataAlive=0;  // millis du dernier tour transféré (pas de backlog moteur).

void applyMotion(Motion m,unsigned pwm) {
  speed_Upper_L=speed_Lower_L=speed_Upper_R=speed_Lower_R=(uint8_t)pwm;
  switch(m){
    case FORWARD:car.Advance();break;case BACK:car.Back();break;
    case LEFT:car.Turn_Left();break;case RIGHT:car.Turn_Right();break;
    case STRAFE_L:car.L_Move();break;case STRAFE_R:car.R_Move();break;
    default:car.Stop();
  }
}
void reply(const char *s,IPAddress ip,uint16_t port){
  udp.beginPacket(ip,port);udp.write((const uint8_t*)s,strlen(s));udp.endPacket();
}

void commandTask(void *) {
  Lease lease;uint16_t ownerPort=0;Motion applied=STOP;unsigned oldPwm=0;
  for(;;){
    uint32_t now=millis();
    if(lease.expired(now)){
      lease.close();car.Stop();applied=STOP;
      xSemaphoreTake(ownerMutex,portMAX_DELAY);ownerActive=false;xSemaphoreGive(ownerMutex);
    }
    // Si le PC ne reçoit plus les scans, on n'entretient pas un mouvement aveugle.
    xSemaphoreTake(ownerMutex,portMAX_DELAY);bool fresh=uint32_t(now-dataAlive)<600;xSemaphoreGive(ownerMutex);
    if(!fresh&&applied!=STOP){car.Stop();applied=STOP;}
    int n=udp.parsePacket();
    if(n>0){
      char buf[128];int got=udp.read(buf,sizeof(buf)-1);buf[got>0?got:0]=0;
      IPAddress ip=udp.remoteIP();uint16_t port=udp.remotePort();
      if(n>=int(sizeof(buf))){vTaskDelay(pdMS_TO_TICKS(2));continue;}
      char tok[33],extra;
      if(sscanf(buf,"HELLO %32s %c",tok,&extra)==1&&tokenValid(tok)){
        if(!lease.active){
          car.Stop();applied=STOP;lease.open(now);ownerPort=port;
          xSemaphoreTake(ownerMutex,portMAX_DELAY);
          strcpy(ownerToken,tok);ownerIP=ip;ownerActive=true;dataAlive=0;
          xSemaphoreGive(ownerMutex);
        }
        if(ip==ownerIP&&port==ownerPort&&!strcmp(tok,ownerToken)){
          char out[48];snprintf(out,sizeof(out),"READY %s\n",tok);reply(out,ip,port);
        }else reply("BUSY\n",ip,port);
      }else{
        Command cmd;
        if(parseCommand(buf,cmd)&&ip==ownerIP&&port==ownerPort&&!strcmp(cmd.token,ownerToken)&&lease.accept(cmd,now)){
          Motion effective=fresh?cmd.motion:STOP;
          if(effective!=applied||cmd.pwm!=oldPwm){applyMotion(effective,cmd.pwm);applied=effective;oldPwm=cmd.pwm;}
          char out[96];snprintf(out,sizeof(out),"SA1 %s %lu %s\n",ownerToken,(unsigned long)cmd.seq,MOTIONS[effective]);reply(out,ip,port);
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

void setup(){
  Serial.begin(115200);car.Init();car.Stop();
  pinMode(32,OUTPUT);digitalWrite(32,HIGH);
  Serial2.setRxBufferSize(8192);Serial2.begin(230400,SERIAL_8N1,33,-1);
  ownerMutex=xSemaphoreCreateMutex();scans=xQueueCreate(1,sizeof(ScanFrame));
  if(!ownerMutex||!scans){Serial.println("Allocation impossible : moteurs arretes.");while(true)delay(1000);}
  WiFi.mode(WIFI_AP);WiFi.setSleep(false);
  if(!WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0))||
     !WiFi.softAP(AP_SSID,AP_PASSWORD,6,0,1)){
    Serial.println("Point acces impossible : moteurs arretes.");while(true)delay(1000);
  }
  udp.begin(COMMAND_PORT);server.begin();
  if(xTaskCreate(commandTask,"commands",6144,nullptr,3,nullptr)!=pdPASS||
     xTaskCreate(scanTask,"scans",6144,nullptr,1,nullptr)!=pdPASS){
    car.Stop();Serial.println("Taches impossibles.");while(true)delay(1000);
  }
  Serial.print("ScanAtlas AP : ");Serial.println(WiFi.softAPIP());
}
void loop(){
  static LidarParser parser;static ScanFrame frame;
  // Un tour par trame, CRC UART puis CRC réseau. La file ne garde que le dernier.
  for(int n=0;n<4096&&Serial2.available();++n)
    if(parser.feed(Serial2.read(),esp_timer_get_time(),frame))xQueueOverwrite(scans,&frame);
  delay(1);
}
