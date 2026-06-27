# src/lib/pov_builder.py
"""Build POV-Ray scenes using Vapory objects and output .pov files for the cluster."""

from vapory import Background, Camera, Finish, LightSource, Pigment, Scene, Sphere, Texture


def build_texture(preset: dict) -> Texture:
    """Build a Vapory Texture object from a preset."""
    pigment = Pigment('rgbt', [
        preset.get("pigment_r", 1.0),
        preset.get("pigment_g", 1.0),
        preset.get("pigment_b", 1.0),
        preset.get("pigment_t", 0.0),
    ])
    finish = Finish(
        'ambient', preset.get("ambient", 0.1),
        'diffuse', preset.get("diffuse", 0.9),
        'reflection', preset.get("reflection", 0.0),
        'specular', preset.get("specular", 0.0),
        'roughness', preset.get("roughness", 0.0),
    )
    return Texture(pigment, finish)


def build_particle_sphere(particle: dict, preset: dict) -> Sphere:
    """Build a Vapory Sphere object from a particle and texture preset."""
    x, y, z = particle["position_x"], particle["position_y"], particle["position_z"]
    size = particle["size"]
    texture = build_texture(preset)
    return Sphere([x, y, z], size, texture)


def build_scene(
    particles: list,
    preset: dict,
    camera_pos: list | None = None,
    look_at: list | None = None,
    light_pos: list | None = None,
    background_color: list | None = None,
) -> Scene:
    """Build a complete POV-Ray scene with particles."""
    if camera_pos is None:
        camera_pos = [0, 2.5, -3]
    if look_at is None:
        look_at = [0, 2.5, 0]
    if light_pos is None:
        light_pos = [1500, 2500, -2500]
    if background_color is None:
        background_color = [0.1, 0.1, 0.1]

    spheres = [build_particle_sphere(p, preset) for p in particles]
    light = LightSource(light_pos, 'color', [1, 1, 1])
    camera = Camera('location', camera_pos, 'look_at', look_at)
    background = Background(background_color)
    return Scene(camera, objects=[light, *spheres], atmospheric=[background])


def write_pov_file(
    scene: Scene,
    output_path: str,
    width: int,
    height: int,
    quality: int,
    antialiasing: bool = False,
) -> str:
    """Write a .pov file from a Vapory scene without rendering.

    Returns the path to the .pov file (for the cluster to render later).
    """
    scene.render(
        outfile=output_path,
        width=width,
        height=height,
        quality=quality,
        antialiasing=antialiasing,
        evaluate=False,
    )
    return output_path
