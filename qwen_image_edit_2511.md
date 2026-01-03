## Basic model info

Model name: qwen/qwen-image-edit-2511
Model description: An enhanced version over Qwen-Image-Edit-2509, featuring multiple improvements including notably better consistency


## Model inputs

- prompt (required): Text instruction on how to edit the given image. (string)
- image (required): Images to use as reference. Must be jpeg, png, gif, or webp. (array)
- aspect_ratio (optional): Aspect ratio for the generated image. (string)
- go_fast (optional): Run faster predictions with additional optimizations. (boolean)
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

### Example (https://replicate.com/p/2krqph3qg5rmr0cv9f48k6th20)

#### Input

```json
{
  "image": [
    "https://replicate.delivery/pbxt/OHhQ8FA8tnsvZWK2uq79oxnWwwfS2LYsV1DssplVT6283Xn5/01.webp",
    "https://replicate.delivery/pbxt/OHhQ8AxCldMQssx9Nt0rHFn9gM0OynvI0uoc3fKpzEV7UUAs/jennai.jpg"
  ],
  "prompt": "On the terrace of a modern art caf\u00e9, two young women are enjoying a leisurely afternoon. The woman on the left is wearing a red sweater. The woman on the right is wearing a gray neck knit sweater and a pair of eye-catching orange wide-leg pants; her left hand is casually tucked into her pocket, and she is tilting her head while talking to her companion.\n\nThey are sitting side-by-side at a small, natural wood-colored table topped with two iced coffees and a small plate of dessert. In the background, there is a city skyline visible through floor-to-ceiling windows and green trees in the distance, with sunlight casting dappled shadows through a parasol.",
  "go_fast": true,
  "aspect_ratio": "3:4",
  "output_format": "webp",
  "output_quality": 95
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/R61hJjCpwkqpBVt7TtCH7Tf7NVRXCDf9dbLQxWWCiHSQRG2VA/out-0.webp"
]
```


### Example (https://replicate.com/p/y50nbq546hrmy0cv9fbsn7asdg)

#### Input

```json
{
  "image": [
    "https://replicate.delivery/pbxt/OHhgsuLbFB02yehUh5qBhQUinmDhO7KhXoBabDC08pQYXACj/replicate-prediction-2zvpdjzd55rmt0cv9fa95zwm44.jpeg"
  ],
  "prompt": "Generate a Christmas-themed image of a beautiful young girl with a \"pure desire\" (innocent yet alluring) aesthetic. Keep the face consistent with the reference.\nCharacter Appearance & Styling\nHair: Loose, low double-braids decorated with colorful fabric balls. Messy, fluffy strands of hair blend naturally with the headpiece.\nHeadpiece: A small, neat, cone-shaped Christmas tree fixed to the top of her head. It features a gold star on top and is richly decorated with colorful lights, gold bells, bow knots, and small red, blue, and gold ornaments.\nFace & Makeup: Fair \"cold-white\" skin, smooth as jade. Natural red-brown eyeshadow gradient. An innocent gaze with a dreamy \"pure desire\" filter.\nClothing: A soft, fluffy red plush top.\nPose & Atmosphere\nAction: Holding a Santa Claus plush toy with both hands. She is tilting her head slightly in a playful, cute, and beautiful pose.\nExpression: Full of festive celebration; a contrast of cuteness and sexiness.\nVibe: A warm, healing Christmas atmosphere.\nTechnical & Artistic Style\nPhotography: Studio soft lighting, 70mm film portrait style. Low contrast, low saturation, delicate film grain, and slight chromatic aberration/glow.\nComposition: Medium shot, warm white background, unique but formal composition.\nArtistic Elements: * The outline of the character is traced with green graffiti.\nThe surrounding white space is filled with cute hand-drawn Christmas doodles (collage style).\nThe silhouette is wrapped in fluorescent red, green, and gold dashed lines and polka dots.\nThe words \"MERRY CHRISTMAS\" are written everywhere in a cute font.",
  "go_fast": true,
  "aspect_ratio": "match_input_image",
  "output_format": "webp",
  "output_quality": 95
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/aFWkYztmfLxbe0vG9cL6kiL1WEDdAm7t6xYAUOMB4uRwgG2VA/out-0.webp"
]
```


### Example (https://replicate.com/p/m115gqtexhrmr0cv9fd8yrvtrc)

#### Input

```json
{
  "image": [
    "https://replicate.delivery/pbxt/OHhkTv4jMNXGZNAn9MEYKck6oWqBXu5AqAOFA3om2SJDJtRK/replicate-prediction-heyne952h5rmy0cv9fcbhrtkv8.jpeg"
  ],
  "prompt": "Generate a four-panel grid (2x2) image. The requirements are as follows:\nCharacter & Panels\nThe character should remain consistent with the reference image, presented across four panels with different poses and expressions:\nTop Left: Both hands raised above the head making double \"V\" (peace) signs. Eyes are wide open, mouth is open, showing a surprised and lively expression.\nTop Right: Both hands cupping the cheeks. Eyes are slightly closed, mouth is pouting, and cheeks have a red blush, showing a cute and coquettish look.\nBottom Left: Head tilted slightly, one eye winking, tongue sticking out, and one hand making a \"V\" sign. A playful and mischievous look.\nBottom Right: Arms crossed over the chest. Brows are slightly furrowed, mouth is pouting, showing a slightly proud and \"tsundere\" (aloof but cute) expression.\nStyling & Aesthetics\nClothing: Remains the same as in the reference image.\nBackground: A colorful background filled with cute cartoon elements like Zootopia.\nArt Style: Overall 2D anime/manga style. Colors are vibrant, and the style is sweet and \"healing\" (comforting).\nDetails: Each small panel has an exquisite cartoon border decoration, filled with a sense of childhood wonder.",
  "go_fast": true,
  "aspect_ratio": "match_input_image",
  "output_format": "jpg",
  "output_quality": 95
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/iyus8leyA5yWU6Ffxhhlk65vutXfj6jUMe120lMJaIW8NaYXB/out-0.jpg"
]
```


### Example (https://replicate.com/p/164rvnw9fdrmr0cv9fjrnh4t3c)

#### Input

```json
{
  "image": [
    "https://replicate.delivery/pbxt/OHhv46uf2nhYbICmcu1IpYaoI5LskMRNz4ipA3wokBFWfRiD/replicate-prediction-y6dfcjva31rmt0cv9fhv7f0550.jpeg"
  ],
  "prompt": "use soft lighting to relight the image.",
  "go_fast": true,
  "aspect_ratio": "match_input_image",
  "output_format": "webp",
  "output_quality": 95
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/ddf3AeMNdGpMmE8EEFmJAlWjv1lvQh6uEMfZJndqVmuf7aYXB/out-0.webp"
]
```


### Example (https://replicate.com/p/vj6ffmp4x1rmt0cv9ft9amkdar)

#### Input

```json
{
  "image": [
    "https://replicate.delivery/pbxt/OHiBDx3nA983Lk8Epo8FwyhSJBVg2LYxG1ShLwURGsPsm7I5/table.png",
    "https://replicate.delivery/pbxt/OHiBD8xImDbyisnQyK3GMe90KdOxty16lDjtqn0vu7vVGRnj/wood.png"
  ],
  "prompt": "Replace the table top wood in Figure 1 with the light wood material from Figure 2",
  "go_fast": true,
  "aspect_ratio": "1:1",
  "output_format": "jpg",
  "output_quality": 95
}
```

#### Output

```json
[
  "https://replicate.delivery/xezq/hLLATq6KrPIjNlrjqguqfIPd5yNvbmq2w5EX55oyOwuTfG2VA/out-0.jpg"
]
```


## Model readme

> # Qwen-Image-Edit-2511
> 
> Edit images with precise control over text, people, and products. This is Qwen's 20 billion parameter image editing model that can combine multiple images, preserve identity, and edit text while keeping the original style intact.
> 
> ## What you can do
> 
> **Multi-image editing**
> 
> Combine multiple images in creative ways. You can merge people with other people, place people in new scenes, or add products to different contexts. The model works best with 1 to 3 input images and supports combinations like person + person, person + product, and person + scene.
> 
> **Precise text editing**
> 
> Add, remove, or modify text in images while preserving the original font, size, and style. The model supports both Chinese and English text editing, letting you directly edit posters, signboards, and other text-heavy images.
> 
> **Semantic editing**
> 
> Modify image content while preserving visual semantics. This lets you change poses, rotate objects, apply style transfers, or create variations of characters while maintaining their identity. You can transform portraits into different artistic styles or generate novel views of objects.
> 
> **Appearance editing**
> 
> Make surgical edits to specific regions while keeping everything else unchanged. Add or remove objects, change backgrounds, modify clothing, or adjust specific elements like the color of a single letter. The model pays attention to details like reflections and lighting consistency.
> 
> **Identity preservation**
> 
> Keep facial features, product identities, or character consistency intact across edits. Whether you're editing portraits, product posters, or character designs, the model preserves what makes each subject recognizable.
> 
> ## How to get good results
> 
> Be specific in your prompts about what should change and what should stay the same. Instead of "make it better," try "enhance the lighting and add warm sunset tones."
> 
> For multi-image editing, clearly reference which elements come from which images. For example, "place the person from the first image on the left and the person from the second image on the right, standing side-by-side in a park."
> 
> When working with people, reference specific characteristics you want to maintain like "preserve the facial features" or "keep the same hairstyle and expression."
> 
> For text editing, mention if you want to preserve or change the font style. The model can either match existing typography or apply new styles based on your description.
> 
> For product posters, describe both the product positioning and the desired background or context.
> 
> ## Replicate
> 
> You can try this model on the Replicate Playground at [replicate.com/playground](https://replicate.com/playground).
