// PoVRay 3.7 Scene File " Pilliars.pov"
// author:  AdmiralMorketh
// date:    9/30/2024
//--------------------------------------------------------------------------

#version 3.7;
global_settings{ assumed_gamma 1.0 }
#default{ finish{ ambient 0.1 diffuse 0.9 }} 

//--------------------------------------------------------------------------

#include "colors.inc"
#include "textures.inc"
#include "glass.inc"
#include "metals.inc"
#include "golds.inc"
#include "stones.inc"
#include "woods.inc"
#include "shapes.inc"
#include "shapes2.inc"
#include "functions.inc"
#include "math.inc"
#include "transforms.inc"

#include "CustomTextures.inc"

#declare WaterTex = 3; // 1 = solid (fast), 2 = transparent (slow), 3 = Custom "WaterTexture" see CustomTextures.inc

// Column settings
#declare ColumnSpacing = 25;
#declare CoumnZ_Offset = 24;
#declare Column_H = 4;

// Fountain Base variables
#declare FountThickness = .25; // Fountain Thickness
#declare FountH = 1;          // Fountain Base Higth
#declare FountR = 2.5;          // Fountain Base Radius

// Fountain Center Variables
#declare FountainCH = 1.5;
#declare FountainCR = .5;
#declare FountainEmitter = .05;



//--------------------------------------------------------------------------
//---------------------------- object definitions --------------------------
//--------------------------------------------------------------------------

// Object definitions

//#declare Brazier = union {
//    cylinder { <0, 0, 0>, <0, 1, 0>, 0.5 texture { StoneTexture } }  // Brazier body
//    sphere { <0, 1, 0>, 0.55 texture { MetalTexture } }  // Brazier bowl
//    cylinder { <0.4, 0, 0>, <0.4, 1, 0>, 0.05 texture { MetalTexture } }  // Supporting leg
//    cylinder { <-0.4, 0, 0>, <-0.4, 1, 0>, 0.05 texture { MetalTexture } }
//    translate <X_Position, 0, Z_Position>  // Position the brazier in the scene
//}

#declare Pilliar =
union {
  cylinder { <1, 0, 0.5>, <1, Column_H, 0.5>, .5 }
  box { <-0.5,0,0>,<2.5,.5,1> }
  box { <-0.5,0,0>,<2.5,.5,1> translate <0, Column_H, 0> }
}

#declare Fountain =
union {
    difference {
       cylinder { <0,0,0>, <0,FountH,0>, FountR }
       // subtract the center
       cylinder { <0,FountThickness,0>, <0,(FountH + FountThickness),0>, (FountR - FountThickness) }
       }
    cylinder { <0,FountThickness,0>, <0,FountainCH,0>, FountainCR }
}

//--------------------------------------------------------------------------
// camera ------------------------------------------------------------------
#declare Camera_0 = camera {/*ultra_wide_angle*/ angle 75      // front view
                            location  <0.0 , 2.5 ,-3.0>
                            right     x*image_width/image_height
                            look_at   <0.0 , 2.5 , 0.0>}
camera{Camera_0}

// sun ---------------------------------------------------------------------
light_source{<1500,2500,-2500> color White*.25}

// sky ---------------------------------------------------------------------
#declare Moon =
light_source{ <-1000, 900, 3000> 
              color White*.75
              looks_like{ sphere{ <0,0,0>, 200 
                                  texture{ pigment{ color White }
                                           normal { bumps 1.5
                                                    scale 20    }
                                           finish { ambient 0.8   
                                                    diffuse 0.2
                                                    phong 1     }
                                         } // end of texture
                                } // end of sphere
                        } //end of looks_like
            } //end of light_source
// sky --------------------------------------------------------------------

// the dark blue
#declare SkyColor = <30/255,4/255,106/255>; 
plane{ <0,1,0>,1 hollow
       texture{ pigment { color rgb SkyColor }
                finish  { ambient 0.25 diffuse 0 } 
              }
       scale 10000}
// the clouds
plane{ <0,1,0>,1 hollow  
       texture{pigment{ bozo turbulence 1.5
                        color_map { [0.5  rgbf <1.0,1.0,1.0,1.0> ]
                                    [0.6  rgb  <1.0,1.0,1.0>     ]
                                    [0.65 rgb  <1.5,1.5,1.5>     ]
                                    [1.0  rgb  <0.5,0.5,0.5>     ] }
                       }
               finish { ambient 0.25 diffuse 0} 
              }      
       scale 500}

// ground ------------------------------------------------------------------

// sea ---------------------------------------------------------------------

plane{ <0,1,0>, 0 
       texture{ Apocalypse
                normal { crackle 0.15 scale <0.35,0.25,0.25> turbulence 0.5 } 
                finish { reflection 0.60}
              }
     }

//--------------------------------------------------------------------------
//---------------------------- objects in scene ----------------------------
//--------------------------------------------------------------------------
//sphere { <0, FountainCH, CoumnZ_Offset-10>, 2 texture { Jade } }
object { Fountain translate <0,0,CoumnZ_Offset-10> texture { Blood_Marble }}
object { Moon }
object { Pilliar translate <-(ColumnSpacing/2), 0, CoumnZ_Offset> texture { LimeStoneTexture } }
object { Pilliar translate <(ColumnSpacing/2), 0, CoumnZ_Offset> texture { LimeStoneTexture } }

// Particle System

union {
   
   blob {
      threshold 1
//PARTICLE_SYSTEM
   }
   
   #if (WaterTex=1) pigment {color rgb  2} #end
   #if (WaterTex=2) pigment {color rgbf 1} #end
   #if (WaterTex=3) texture {WaterTexture} #end
   finish {reflection {0.1,0.9 fresnel} conserve_energy phong 1 phong_size 20}
   interior {ior 1.33}
}