#include "Create_Stones.inc"

// -------------------------------------------------------------------------
// Textures ----------------------------------------------------------------

#declare LimeStoneTexture = 
texture{ WeatheredLimeStone
    normal{wrinkles 0.9}
    scale <1,1,1>*0.075
}

#declare Jade = 
pigment {
    marble
    turbulence 1.8
    color_map { Jade_Map }
}

// Water texture definition
#declare WaterTexture =
texture {
    pigment { rgbt <0.7, 0.9, 1.0, 0.85> }  // Light blue color with high transparency
    finish {
        ambient 0.1
        diffuse 0.9
        reflection 0.4  // Slight reflection
        specular 0.9  // Sharp highlights
        roughness 0.001  // Smooth surface for a shiny look
    }
    interior {
        ior 1.33  // Index of refraction for water
    }
}


#declare Azerite_Map = pigment {
    bozo
    turbulence 0.5
    lambda 1.5
    omega 0.8
    octaves 5
    frequency 3
    color_map { 
            [0.0 rgbt <1.0, 0.8, 0.3, 0.1>]  // Golden-yellow with some transparency
            [0.5 rgbt <0.0, 0.4, 0.8, 0.1>]  // Bright blue with transparency
            [1.0 rgbt <1.0, 0.8, 0.3, 0.1>]  // Return to golden-yellow
    }
    scale <0.25, 0.25, 0.25>
}

// Define a vibrant Azerite texture
#declare AzeriteTexture = texture {
    pigment { Azerite_Map }  // Bright blue with some transparency
    finish {
        ambient 0.1
        diffuse 0.5
        reflection 0.5  // Reflective properties to simulate liquid shine
        brilliance 3     // Enhance the shiny look
        refraction 1.5   // Higher index of refraction for liquids
    }
}

#declare SmokeTexture = texture {
    pigment {
        gradient y
        color_map {
            [0.0 color rgbt <0.1, 0.1, 0.1, 0>]  // Dark gray near the fire
            [1.0 color rgbt <0, 0, 0, 0.8>]      // Fading to transparent black
        }
    }
    finish {
        ambient 0.3
        diffuse 0.5
    }
}

#declare FireTexture = texture {
    pigment {
        gradient y
        color_map {
            [0.0 color rgbt <1, 0.5, 0, 0>]  // Bright orange near the base
            [0.4 color rgbt <1, 0, 0, 0.1>]  // Red further up
            [1.0 color rgbt <0, 0, 0, 1>]    // Fading to transparent black at the top
        }
    }
    finish {
        ambient 0.8
        diffuse 0.4
        emission 1.0
    }
}


#declare SciFiTexture = texture {
    // Base layer: stone
    pigment {
        granite  // Granite pattern for rough stone look
        color_map {
            [0.0 color rgb <0.2, 0.2, 0.2>]  // Dark stone base
            [0.4 color rgb <0.3, 0.3, 0.3>]  // Mid-gray stone
            [0.8 color rgb <0.5, 0.5, 0.5>]  // Lighter gray highlights
            [1.0 color rgb <0.7, 0.7, 0.7>]  // Shiny stone specs
        }
        scale 0.5
    }
    finish {
        ambient 0.2
        diffuse 0.6
        specular 0.1  // Slight shine for the stone
        roughness 0.8  // Keep stone surface rough
    }
}

#declare MetalInlay = texture {
    // Top layer: metallic inlay
    pigment {
        checker  // Checker pattern for a tech-like look
        color_map {
            [0.0 color rgb <0.6, 0.6, 0.6>]  // Shiny metal
            [1.0 color rgb <0.2, 0.2, 0.2>]  // Dark metal grid
        }
        scale 0.2
    }
    finish {
        ambient 0.3
        diffuse 0.4
        specular 1.0  // High reflectivity for the metal
        metallic  // Metallic finish
        reflection 0.6  // Reflective, but not a mirror
    }
    normal {
        bumps 0.2  // Subtle texture on the metal surface
        scale 0.1
    }
}

#declare SciFiStoneMetal = texture {
    // Combine both textures
    texture_map {
        [0.0 SciFiTexture]
        [0.4 MetalInlay]
    }
    scale <0.5, 0.5, 0.5>  // Overall scale for both textures
}

//def GetCITexture():
//    """Returns the CI Texture
//    Green and Black Marble with touches of sky blue"""
//    CI_ColorMap = ColorMap([0.0,  'rgb', [0.0, 0.0, 0.0]],
//                           [0.7,  'rgb', [0.0, 0.3, 0.0]],
//                           [0.5,  'rgb', [0.0, 0.7, 0.0]],
//                           [0.6,  'rgb', [0.0, 0.2, 0.0]],
//                           [0.65, 'rgb', [0.0, 1.0, 1.0]],
//                           [0.75, 'rgb', [0.0, 0.2, 0.0]],
//                           [0.8,  'rgb', [0.0, 0.5, 0.0]],
//                           [1.0,  'rgb', [0.0, 1.0, 0.0]])
//
//    return Texture(Pigment('marble', 'turbulence', 2.75, CI_ColorMap, 'scale', 2.5, 'rotate', [0, 7.5 ,0]))