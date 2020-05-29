# Render Marker Frames

Blender addon to quickly render out time line preview ranges defined by markers into separate output folders.


## What is this useful for?

The narrow use case for which this is design to more rapidly generate image frame sequences for use as overlays in longer videos. The workflow is as follows:

1) Render out a previz movie file of the longform video from whatever video editing program
2) Bring into blender as a background movie (and add a sound object for the sound)
3) Add markers for the specific sections that need custom animation
4) Animate for those ranges
5) Render animation for a specific range or all ranges at once, outputting to individual separate folders per range (defined by two marker bookends)
6) Import the image sequences from each range as its own image clip into the video editor.

This workflow still requires manually loading the images sequences into the right position in the video editing program, but avoids the need to rendering out loads of blank full sized image files when only a small % of the overall frames have any animation that really needs rendering.

This is useful as rendering in the context of the project where this was made because we are using Eevee realtime rendering (in fact, rendering the viewport and not even the full F12 render) - but with many re-renders likely. Thus, rendering lots of blank frames when only a few seconds of animation is required is a pain, but the easiest way to animate is still with the in-place video reference background (and there is no need to create new scenes/sequences for every single time we need an animation range rendered).
