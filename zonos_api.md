# Zonos API Documentation

## Base URL

[API Documentation](https://52a139f01540aa0a5c.gradio.live/)

## Installation

To interact with the API, install the Python client:

```sh
pip install gradio_client
```

## Endpoints

### 1. `/update_ui`

#### Request

```python
from gradio_client import Client

client = Client("https://52a139f01540aa0a5c.gradio.live/")
result = client.predict(
    model_choice="Zyphra/Zonos-v0.1-transformer",
    api_name="/update_ui"
)
print(result)
```

#### Parameters

- `model_choice`: Literal[`'Zyphra/Zonos-v0.1-transformer'`, `'Zyphra/Zonos-v0.1-hybrid'`] (Default: `'Zyphra/Zonos-v0.1-transformer'`)

#### Response

Returns a tuple of 19 elements:

1. `str` - Text to Synthesize
2. `Literal[...]` - Language Code
3. `filepath` - Optional Speaker Audio
4. `filepath` - Optional Prefix Audio
5. `float` - Happiness
6. `float` - Sadness
7. `float` - Disgust
8. `float` - Fear
9. `float` - Surprise
10. `float` - Anger
11. `float` - Other
12. `float` - Neutral
13. `float` - VQ Score
14. `float` - Fmax (Hz)
15. `float` - Pitch Std
16. `float` - Speaking Rate
17. `float` - DNSMOS Overall
18. `bool` - Denoise Speaker?
19. `list[Literal[...]]` - Unconditional Keys

---

### 2. `/update_ui_1`

#### Request

```python
from gradio_client import Client

client = Client("https://52a139f01540aa0a5c.gradio.live/")
result = client.predict(
    model_choice="Zyphra/Zonos-v0.1-transformer",
    api_name="/update_ui_1"
)
print(result)
```

#### Parameters

- `model_choice`: Literal[`'Zyphra/Zonos-v0.1-transformer'`, `'Zyphra/Zonos-v0.1-hybrid'`] (Default: `'Zyphra/Zonos-v0.1-transformer'`)

#### Response

Returns the same tuple structure as `/update_ui`.

---

### 3. `/generate_audio`

#### Request

```python
from gradio_client import Client, handle_file

client = Client("https://52a139f01540aa0a5c.gradio.live/")
result = client.predict(
    model_choice="Zyphra/Zonos-v0.1-transformer",
    text="Zonos uses eSpeak for text to phoneme conversion!",
    language="en-us",
    speaker_audio=handle_file('https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav'),
    prefix_audio=handle_file('https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav'),
    e1=1,
    e2=0.05,
    e3=0.05,
    e4=0.05,
    e5=0.05,
    e6=0.05,
    e7=0.1,
    e8=0.2,
    vq_single=0.78,
    fmax=24000,
    pitch_std=45,
    speaking_rate=15,
    dnsmos_ovrl=4,
    speaker_noised=False,
    cfg_scale=2,
    min_p=0.15,
    seed=420,
    randomize_seed=True,
    unconditional_keys=["emotion"],
    api_name="/generate_audio"
)
print(result)
```

#### Parameters

- `model_choice`: Literal[`'Zyphra/Zonos-v0.1-transformer'`, `'Zyphra/Zonos-v0.1-hybrid'`] (Default: `'Zyphra/Zonos-v0.1-transformer'`)
- `text`: `str` (Default: "Zonos uses eSpeak for text to phoneme conversion!")
- `language`: `Literal[...]` (Default: `'en-us'`)
- `speaker_audio`: `filepath` (Required)
- `prefix_audio`: `filepath` (Default: Sample Audio URL)
- `e1-e8`: `float` (Default varies per parameter)
- `vq_single`: `float` (Default: `0.78`)
- `fmax`: `float` (Default: `24000`)
- `pitch_std`: `float` (Default: `45`)
- `speaking_rate`: `float` (Default: `15`)
- `dnsmos_ovrl`: `float` (Default: `4`)
- `speaker_noised`: `bool` (Default: `False`)
- `cfg_scale`: `float` (Default: `2`)
- `min_p`: `float` (Default: `0.15`)
- `seed`: `float` (Default: `420`)
- `randomize_seed`: `bool` (Default: `True`)
- `unconditional_keys`: `list[Literal[...]]` (Default: `['emotion']`)

#### Response

Returns a tuple of 2 elements:

1. `filepath` - Generated Audio
2. `float` - Seed Number

