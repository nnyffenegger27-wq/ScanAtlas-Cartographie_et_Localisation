#pragma once
#include <Arduino.h>
#include <esp_arduino_version.h>
#include "motor_config.h"
#include "protocol.h"

class MotorPWM {
  bool ready=false;
  void write(unsigned channel,unsigned duty){
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(MOTOR_PINS[channel],duty);
#else
    ledcWrite(channel,duty);
#endif
  }
public:
  bool begin(){
    for(int i=0;i<8;++i){
      int p=MOTOR_PINS[i];
      bool gpio=p==0||p==2||p==4||p==5||(p>=12&&p<=19)||(p>=21&&p<=23)||(p>=25&&p<=27);
      if(!gpio)return false; // ESP32 classique, hors flash, console et lidar.
      for(int j=0;j<i;++j)if(p==MOTOR_PINS[j])return false;
    }
    for(int i=0;i<4;++i){
      if(WHEEL_MOTOR[i]<0||WHEEL_MOTOR[i]>3||(WHEEL_SIGN[i]!=1&&WHEEL_SIGN[i]!=-1))return false;
      for(int j=0;j<i;++j)if(WHEEL_MOTOR[i]==WHEEL_MOTOR[j])return false;
    }
    for(int i=0;i<8;++i){
      pinMode(MOTOR_PINS[i],OUTPUT);digitalWrite(MOTOR_PINS[i],LOW);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
      if(!ledcAttach(MOTOR_PINS[i],MOTOR_PWM_HZ,8))return false;
#else
      if(ledcSetup(i,MOTOR_PWM_HZ,8)==0)return false;
      ledcAttachPin(MOTOR_PINS[i],i);
#endif
    }
    ready=true;stop();return true;
  }
  void stop(){if(ready)for(int i=0;i<8;++i)write(i,0);}
  void wheel(unsigned motor,int power){
    if(!ready||motor>3)return;
    unsigned a=2*motor,b=a+1;
    // Mettre d'abord les deux entrées à zéro lors d'un changement de sens.
    write(a,0);write(b,0);
    if(power>0)write(a,min(power,255));
    else if(power<0)write(b,min(-power,255));
  }
  void apply(Motion m,unsigned pwm){
    // Roues mecanum en X : FL FR RL RR. Profil et polarités configurables.
    static const int signs[7][4]={{0,0,0,0},{1,1,1,1},{-1,-1,-1,-1},
       {-1,1,-1,1},{1,-1,1,-1},{-1,1,1,-1},{1,-1,-1,1}};
    if(unsigned(m)>6){stop();return;}
    pwm=min(pwm,100u);  // Même plafond que le protocole et l'application.
    for(int i=0;i<4;++i)wheel(WHEEL_MOTOR[i],signs[m][i]*WHEEL_SIGN[i]*int(pwm));
  }
};
