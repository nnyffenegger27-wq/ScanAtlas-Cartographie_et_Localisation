#pragma once
// Profil PWM proposé à partir du câblage relevé, à vérifier sur chaque robot.
// Entrées fixes de la carte moteur : M1A M1B M2A M2B M3A M3B M4A M4B.
constexpr int MOTOR_PINS[8]={5,18,19,21,2,4,16,17};
// Ordre logique : avant gauche, avant droite, arrière gauche, arrière droite.
// Chaque valeur désigne M1..M4 (indices 0..3). L'emplacement reste à confirmer.
constexpr int WHEEL_MOTOR[4]={0,1,2,3};
constexpr int WHEEL_SIGN[4]={1,1,1,1};
constexpr unsigned MOTOR_PWM_HZ=20000;

// Passer à true uniquement pour le diagnostic série, roues levées.
// Wi-Fi et lidar ne démarrent pas dans ce mode.
constexpr bool MOTOR_DIAGNOSTIC=false;
