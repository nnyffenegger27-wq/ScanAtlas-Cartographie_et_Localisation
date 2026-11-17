#pragma once
#include <Arduino.h>
#include <esp_arduino_version.h>
#include "motor_config.h"
#include "motor_common.h"

// Pilote PWM direct : huit sorties LEDC sur les entrées M1A..M4B de la carte moteur.
class MotorPWM : public MotorDrive<MotorPWM> {
  bool ready=false;
  void write(unsigned channel,unsigned duty){
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(MOTOR_PINS[channel],duty);
#else
    ledcWrite(channel,duty);
#endif
  }
public:
  static const char *name(){return "PWM";}
  static int motorOf(int wheel){return WHEEL_MOTOR[wheel];}
  static int signOf(int wheel){return WHEEL_SIGN[wheel];}
  bool begin(){
    if(!motorPinsValid(MOTOR_PINS,8))return false;
    if(!motorWheelMapValid(WHEEL_MOTOR,WHEEL_SIGN))return false;
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
};
