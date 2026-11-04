"""Vérifications hôte du pilote I2C et du choix PWM / I2C, sans moteur réel."""
from pathlib import Path
import subprocess
import tempfile
import unittest

DOSSIER = Path(__file__).resolve().parents[1]/'firmware/ScanAtlas_WiFi'

ARDUINO = '''#pragma once
#include <algorithm>
#include <cstdint>
using std::min;
#define OUTPUT 1
#define LOW 0
inline void pinMode(int,int){} inline void digitalWrite(int,int){}
extern unsigned values[40];
inline double ledcSetup(int,int,int){return 1;}
inline void ledcAttachPin(int,int){}
inline bool ledcAttach(int,int,int){return true;}
inline void ledcWrite(int n,unsigned p){values[n]=p;}
'''

# Faux bus : la vraie classe mecanumCar (MecanumCar_v2.h) avec PWM_OUT enregistré.
I2C_MAIN = r'''#include "motor_driver.h"
#include <cassert>
#include <vector>
unsigned values[40]={0};
uint8_t speed_Upper_L,speed_Lower_L,speed_Upper_R,speed_Lower_R;
static int sda=-1,scl=-1;
static unsigned ch[9];                       // dernière valeur par canal 1..8
static std::vector<std::pair<int,int>> log_;  // ordre des écritures
mecanumCar::mecanumCar(int a,int b){SDA=a;SCL=b;sda=a;scl=b;}
void mecanumCar::PWM_OUT(uint8_t c,uint8_t p){assert(c>=1&&c<=8);ch[c]=p;log_.push_back({c,p});}
static void expect(unsigned c1,unsigned c2,unsigned c3,unsigned c4,unsigned c5,unsigned c6,unsigned c7,unsigned c8){
  unsigned e[9]={0,c1,c2,c3,c4,c5,c6,c7,c8};
  for(int i=1;i<=8;++i)assert(ch[i]==e[i]);
}
int main(){
#if MOTOR_DRIVER != MOTOR_DRIVER_I2C
#error "ce test attend MOTOR_DRIVER_I2C"
#endif
  static_assert(sizeof(MotorDriver)>0,"");
  MotorDriver car;assert(car.name()[0]=='I');
  assert(car.begin());assert(sda==I2C_SDA_PIN&&scl==I2C_SCL_PIN);
  for(int i=1;i<=8;++i)assert(ch[i]==0);
  // Avant : les quatre roues poussent sur le canal pair du moteur correspondant.
  car.apply(FORWARD,65);expect(0,65,0,65,0,65,0,65);
  car.apply(BACK,65);expect(65,0,65,0,65,0,65,0);
  car.stop();expect(0,0,0,0,0,0,0,0);
  // Commande combinée, roues FL FR RL RR -> Upper_L(3-4) Upper_R(1-2) Lower_L(7-8) Lower_R(5-6).
  car.drive(60,0,0);expect(0,60,0,60,0,60,0,60);
  car.drive(0,50,0); // gauche : FL et RR reculent, FR et RL avancent
  expect(0,50,50,0,50,0,0,50);  // FR=ch2, FL=ch3 (recul), RR=ch5 (recul), RL=ch8
  car.drive(0,0,100); // rotation gauche : côté gauche recule, côté droit avance
  expect(0,100,100,0,0,100,100,0);
  car.drive(0,0,0);expect(0,0,0,0,0,0,0,0);
  // Changement de sens : le canal opposé tombe à zéro avant l'activation.
  car.drive(60,0,0);log_.clear();car.wheel(0,-40);
  assert(log_.size()==2&&log_[0]==std::make_pair(2,0)&&log_[1]==std::make_pair(1,40));
  log_.clear();car.wheel(0,40);
  assert(log_.size()==2&&log_[0]==std::make_pair(1,0)&&log_[1]==std::make_pair(2,40));
  car.drive(60,0,0);car.apply(STOP,65);expect(0,0,0,0,0,0,0,0);
  car.apply(FORWARD,250);assert(ch[2]==100);  // plafond 100 comme le PWM
  car.stop();
  return 0;
}
'''

SELECTEUR = r'''#include "motor_driver.h"
unsigned values[40]={0};
#if MOTOR_DRIVER == MOTOR_DRIVER_I2C
uint8_t speed_Upper_L,speed_Lower_L,speed_Upper_R,speed_Lower_R;
mecanumCar::mecanumCar(int a,int b){SDA=a;SCL=b;}
void mecanumCar::PWM_OUT(uint8_t,uint8_t){}
#endif
int main(){MotorDriver c;return c.begin()&&c.name()[0]==NOM?0:1;}
'''

VALIDATION = r'''#include "motor_common.h"
#include <cassert>
int main(){
  assert(motorGpioUsable(19)&&motorGpioUsable(21)&&motorGpioUsable(5));
  assert(!motorGpioUsable(1)&&!motorGpioUsable(3)&&!motorGpioUsable(6)&&!motorGpioUsable(32)&&!motorGpioUsable(33)&&!motorGpioUsable(34));
  const int ok[2]={19,21},twin[2]={19,19},bad[2]={19,33};
  assert(motorPinsValid(ok,2)&&!motorPinsValid(twin,2)&&!motorPinsValid(bad,2));
  const int m[4]={1,0,3,2},s[4]={1,1,-1,1},dup[4]={1,1,3,2},range[4]={1,0,3,4},sign0[4]={1,0,1,1};
  assert(motorWheelMapValid(m,s)&&!motorWheelMapValid(dup,s)&&!motorWheelMapValid(range,s)&&!motorWheelMapValid(m,sign0));
}
'''


def compiler(d, source, nom, version=2, extra=()):
    (d/'esp_arduino_version.h').write_text(f'#define ESP_ARDUINO_VERSION_MAJOR {version}\n')
    (d/f'{nom}.cpp').write_text(source)
    resultat = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(d), '-I', str(DOSSIER), *extra,
                               str(d/f'{nom}.cpp'), '-o', str(d/nom)], capture_output=True, text=True)
    if resultat.returncode:
        raise AssertionError(resultat.stderr)
    return d/nom


class MotorI2CTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        (self.d/'Arduino.h').write_text(ARDUINO)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pilote_i2c_canaux_sens_et_ordre(self):
        programme = compiler(self.d, I2C_MAIN, 'i2c', extra=['-DMOTOR_DRIVER=2'])
        subprocess.run([str(programme)], check=True, capture_output=True)

    def test_selection_du_pilote(self):
        for valeur, nom in ((1, "'P'"), (2, "'I'")):
            for version in (2, 3):
                programme = compiler(self.d, SELECTEUR, 'sel', version, ['-DMOTOR_DRIVER=%d' % valeur, '-DNOM=%s' % nom])
                subprocess.run([str(programme)], check=True, capture_output=True)

    def test_pilote_inconnu_refuse_a_la_compilation(self):
        with self.assertRaises(AssertionError):
            compiler(self.d, SELECTEUR, 'sel', 2, ['-DMOTOR_DRIVER=7', '-DNOM=1'])

    def test_validation_broches_et_roues(self):
        programme = compiler(self.d, VALIDATION, 'val')
        subprocess.run([str(programme)], check=True, capture_output=True)

    def test_defaut_est_pwm(self):
        texte = (DOSSIER/'motor_config.h').read_text(encoding='utf-8')
        self.assertIn('#define MOTOR_DRIVER MOTOR_DRIVER_PWM', texte)


if __name__ == '__main__':
    unittest.main()
