## Basic model info

Model name: qwen/qwen-image-2512
Model description: Qwen Image 2512 is an improved version of Qwen Image with more realistic human generation, finer textures, and stronger text rendering


## Model inputs

- prompt (required): Text prompt for image generation. (string)
- negative_prompt (optional): Negative prompt for image generation. (string)
- image (optional): Input image for image2image generation. The aspect ratio of your output will match this image. (string)
- strength (optional): Strength for image2image generation. 1.0 corresponds to full destruction of information in image. (number)
- aspect_ratio (optional): Aspect ratio for the generated image. (string)
- width (optional): Width of the generated image. Only used when aspect_ratio=custom. Must be a multiple of 16. (integer)
- height (optional): Height of the generated image. Only used when aspect_ratio=custom. Must be a multiple of 16. (integer)
- guidance (optional): Guidance for generated image. Use higher values for stronger prompt adherence. (number)
- num_inference_steps (optional): Number of denoising steps. Use less steps for faster generation. (integer)
- go_fast (optional): Use the model with additional optimizations for faster generation. (boolean)
- seed (optional): Random seed. Set for reproducible generation. (integer)
- output_format (optional): Format of the output images. (string)
- output_quality (optional): Quality when saving the output images, from 0 to 100. 100 is best quality, 0 is lowest quality. Not relevant for .png outputs. (integer)
- disable_safety_checker (optional): Disable safety checker for generated images. (boolean)


## Model output schema

{
  "type": "array",
  "items": {
    "type": "string",
    "format": "uri"
  },
  "title": "Output"
}

If the input or output schema includes a format of URI, it is referring to a file.


## Example inputs and outputs

Use these example outputs to better understand the types of inputs the model accepts, and the types of outputs the model returns:

### Example (https://replicate.com/p/9ksdjh862drmw0cvekb8qa9g74)

#### Input

```json
{
  "prompt": "This is a modern slide with a deep blue gradient background. The title is \"Qwen Image 2512 Major Release\" in white sans serif bold font. \nOn the left a female portrait lacks detail. On the right a highly realistic young woman's portrait close to photographic quality. An arrow links the images labeled \"2512 Quality Upgrade\" \nFaint glow effects besides the arrow enhance dynamism\nText below reads: \"More realistic texture, finer details, enhanced text rendering\"",
  "go_fast": true,
  "guidance": 4,
  "strength": 0.8,
  "aspect_ratio": "16:9",
  "output_format": "webp",
  "output_quality": 95,
  "negative_prompt": " ",
  "num_inference_steps": 40
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/5m3MbcyKrjoKLNuRet82TBla9EZpdCU55KpI37fULyFEbu4VA/out-0.webp"
]
```


### Example (https://replicate.com/p/tg3bkqhwtsrmy0cvekwtnb5sf8)

#### Input

```json
{
  "prompt": "A cinematic photograph of a London Underground tube station platform with the main focus on a large TfL red roundel sign reading \"REPLICATE STATION\" in white Johnston typeface, below it are four classic blue and white enamel directional signs in a horizontal row reading \"Qwen Image,\" \"Runway Aleph,\" \"ByteDance OmniHuman,\" and \"Wan 2.2\" each with white directional arrows, an elegant woman in a flowing white dress stands on the platform with her long dark hair and dress caught in motion from the wind of a red tube train passing behind her in motion blur, the composition emphasizes the prominent station signage in the upper portion of the frame, characteristic curved tunnel walls with Victorian cream and burgundy tiles, warm golden tungsten lighting creating atmospheric glow, the yellow \"Mind the Gap\" safety line visible on the platform edge, shot with shallow depth of field focusing on the signage and woman while the moving train creates streaked motion blur in the background",
  "go_fast": true,
  "guidance": 4,
  "strength": 0.8,
  "aspect_ratio": "16:9",
  "output_format": "webp",
  "output_quality": 95,
  "negative_prompt": " ",
  "num_inference_steps": 40
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/UEwRsSCVgqIpOV85Bi6cvUXlLgKetUuv08MfK2eexjHh87iXB/out-0.webp"
]
```


### Example (https://replicate.com/p/4b9nvmbm75rmw0cvekx9nxw1tc)

#### Input

```json
{
  "prompt": "A dynamic portrait photo of a woman, unusual lighting, creative composition, cyan and purple uplighting",
  "go_fast": true,
  "guidance": 4,
  "strength": 0.8,
  "aspect_ratio": "3:4",
  "output_format": "webp",
  "output_quality": 95,
  "negative_prompt": " ",
  "num_inference_steps": 40
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/YSQKUIuuMFouAdlhiC4HJJGqWvyXNhs4x2AFxdCSMqNGwLeKA/out-0.webp"
]
```


## Model readme

> # Qwen-Image-2512
> 
> Qwen-Image-2512 is the December 2024 update to Alibaba Cloud's text-to-image model. It generates photorealistic images with improved human rendering, natural textures, and accurate text—especially in Chinese.
> 
> After over 10,000 rounds of blind evaluation on AI Arena, Qwen-Image-2512 ranks as the strongest open-source image generation model, while staying competitive with closed-source systems.
> 
> ## What's improved
> 
> **More realistic people**
> 
> The model dramatically reduces the "AI-generated" look in human portraits. It captures age-appropriate details like wrinkles, skin texture, and natural facial features. Hair strands are rendered individually instead of blurred together, and subtle expressions come through more naturally.
> 
> **Finer natural detail**
> 
> Landscapes, animal fur, and organic textures are rendered with significantly more detail. The model better captures the complexity of natural surfaces and environmental context.
> 
> **Better text rendering**
> 
> Text quality has improved across the board—better layout, more accurate character rendering, and more faithful composition when mixing text and images. This is especially strong for Chinese text, which has thousands of complex characters that need pixel-perfect accuracy.
> 
> **Improved prompt following**
> 
> The model better follows semantic instructions in your prompts. If you specify "body leaning slightly forward," the model actually captures that posture. Details in your prompt translate more reliably to the final image.
> 
> ## Example outputs
> 
> Here are some examples showing what the model can do:
> 
> ### Photorealistic portraits
> 
> The model handles detailed human features, natural lighting, and environmental context. Skin texture, hair detail, and subtle expressions all come through clearly.
> 
> ### Text rendering in images
> 
> Whether you need English or Chinese text, the model integrates typography seamlessly into the scene. Complex layouts with multiple text elements maintain readability and visual coherence.
> 
> ### Natural scenes
> 
> Fine details in landscapes, animal fur, and organic textures show notable improvement over the August release.
> 
> ## How to use it
> 
> Give the model a detailed text prompt describing what you want to see. The more specific you are about composition, lighting, style, and details, the better your results will be.
> 
> For best results with text in images, be explicit about what the text should say and where it should appear in the scene.
> 
> The model supports various aspect ratios and artistic styles—from photorealistic to impressionistic to anime aesthetics.
> 
> ## Technical details
> 
> Qwen-Image-2512 is built on a 20 billion parameter Multimodal Diffusion Transformer architecture. The base Qwen-Image model was released in August 2024, and this December update brings substantial improvements across all capabilities.
> 
> The model was developed by Alibaba Cloud's Qwen team and is released under the Apache 2.0 license.
> 
> For more details, check out the [model card](https://huggingface.co/Qwen/Qwen-Image-2512) on Hugging Face.
> 
> ## Try it yourself
> 
> You can experiment with Qwen-Image-2512 in the Replicate Playground at replicate.com/playground
