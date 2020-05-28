# Openwhisk cloud function for converting and aligning audio tracks

## To create the audio aligner function

```ic fn action create calculate_alignment calculate_alignment.py --docker hammertoe/librosa_ml:latest --param bucket <bucket> --param endpoint <endpoint> --param apikey <api key>```

## To invoke the function

```matt@Matts-MBP audio-aligner-service % ic fn action invoke calculate_alignment -r -p reference leader.mp4 -p part sarah1.webm
{
    "err": 0.1325956771107738,
    "offset": -290.24943310657596,
    "part": "sarah1.webm",
    "reference": "leader.mp4"
}
```
