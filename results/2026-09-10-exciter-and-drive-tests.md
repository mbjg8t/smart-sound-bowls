# Smart Sound Bowl - Exciter and Drive Testing

**Date:** September 10, 2026

## Purpose

Testing focused on determining:

1. How much exciter power is actually required to drive the test crystal bowl.
2. How exciter size and placement affect coupling and damping.
3. Whether the bowl resonance can be automatically detected using the Teensy piezo feedback system.
4. Whether bowl amplitude can be controlled in closed loop.
5. How to drive the bowl smoothly enough for an actual sound-bath experience without audible or mechanical on/off transitions.

The major result is that exciter power requirements are much lower than originally expected.

The 20 W exciter is substantially oversized for this bowl.

A 1 W exciter mounted on the bowl sidewall has more than enough drive authority and is currently the preferred direction.

---

# Test System

Current relevant hardware:

- Raspberry Pi 4
- PCM5122 I2S DAC
- Class-D amplifier
- Teensy 4.0
- Piezo vibration pickup
- Crystal sound bowl
- 20 W exciter used in earlier testing
- 1 W exciter used in current testing

Piezo feedback:

- Piezo signal -> Teensy A0
- Teensy ADC sampling: 20 ksample/sec
- 12-bit ADC
- Teensy sends approximately 100 ms measurement windows to Raspberry Pi
- YIN frequency detector used for vibration-frequency estimation
- Piezo peak-to-peak ADC amplitude used as the principal bowl-response measurement

Typical quiet piezo level has been approximately:

    50-90 ADC P2P

Bowl fundamental resonance throughout these tests has remained approximately:

    529 Hz

---

# Automatic Resonance Detection

The resonance-detection system now performs:

1. Coarse frequency sweep
2. Piezo amplitude measurement
3. Fine frequency sweep around the strongest response
4. Automatic reduction in DAC amplitude if the Teensy ADC clips
5. Parabolic interpolation around the response peak
6. Final resonance estimate

The YIN detector independently estimates the actual bowl vibration frequency.

Typical confidence near resonance:

    ~0.94-0.96

This has proven reliable enough to automatically locate the bowl resonance without hardcoding the expected bowl frequency.

---

# Earlier 20 W Exciter - Sidewall

The 20 W exciter was tested at a working sidewall position.

Automatic resonance result:

    Resonance:             529.154 Hz
    Sweep peak P2P:        233
    Driven median P2P:     219.5
    Driven maximum P2P:    231
    Measured drive freq:   ~529.5 Hz
    DAC amplitude:         0.150%
    ADC clipping:          No

Ringdown:

    Initial ringdown P2P:  233
    Decay to 50%:          0.20 sec
    Decay to 36.8%:        0.20 sec
    Decay to 20%:          0.30 sec

This provided a useful baseline for comparing other exciter configurations.

---

# Exciter Placement Testing

## Base mounting

The larger exciter was tested at the base of the bowl, both inside and outside.

Results were substantially worse and much less repeatable than sidewall mounting.

At approximately 0.15% drive:

    Response remained close to noise floor
    ~50-60 P2P

At approximately 1% drive:

    Response was still generally near noise floor
    ~50-60 P2P

At approximately 2% drive:

    Results became inconsistent.

Some runs showed weak coupling, while other runs produced a strong response and ADC clipping.

This suggests the base mounting configuration is highly dependent on exact physical contact and can transition between poorly coupled and strongly coupled mechanical states.

Conclusion:

    Base mounting is not currently attractive.

Sidewall mounting has been much more efficient and repeatable.

---

# Exciter Placement Reference

Commercial sound-bowl excitation systems investigated previously also place their exciter on the bowl sidewall rather than at the bottom.

A useful initial placement region is approximately:

    1/3 to 1/2 of bowl height

However, our current 1 W exciter has been mounted approximately:

    5/8 of the way up the sidewall

and has demonstrated extremely strong coupling.

Placement clearly matters at least as much as exciter wattage.

---

# 1 W Exciter - Sidewall at Approximately 5/8 Height

The 1 W exciter was mounted approximately 5/8 of the way up the sidewall.

This configuration immediately demonstrated that 1 W is more than sufficient to drive this bowl.

## High-drive behavior

The bowl was driven strongly enough during early testing to repeatedly clip the Teensy ADC.

The autotune system automatically reduced the sweep amplitude through approximately:

    1.000%
    0.600%
    0.360%
    0.216%
    0.130%

This alone demonstrates the very high mechanical gain available around resonance.

---

# 1 W Automatic Resonance Test

At the final unclipped sweep amplitude:

    DAC sweep amplitude:       0.130%
    Measured peak point:       528.750 Hz
    Interpolated resonance:    528.691 Hz
    Peak median P2P:           281
    Maximum P2P:               300
    Piezo measured frequency:  529.100 Hz
    YIN confidence:            0.950

Representative response around resonance:

    Drive Hz    Median P2P
    --------    ----------
    527.0       195.5
    527.25      223.5
    527.5       237.5
    527.75      261.0
    528.0       234.0
    528.25      278.0
    528.5       276.0
    528.75      281.0
    529.0       267.0
    529.25      216.5
    529.5       202.0

The response shows a clear mechanical resonance around 528.7-529 Hz.

---

# 1 W Ringdown Test

The final drive portion of this particular test was manually changed to approximately 1%.

This was intentionally/accidentally much stronger than necessary and caused Teensy ADC clipping.

Results:

    Resonance:             528.691 Hz
    Baseline P2P:          79
    Driven median P2P:     821
    Driven maximum P2P:    842
    Measured drive freq:   528.80 Hz
    Initial ringdown P2P:  830
    Decay to 50%:          0.52 sec
    Decay to 36.8%:        0.52 sec
    Decay to 20%:          0.62 sec
    ADC clipping:          Yes

These decay values should NOT be treated as an exact apples-to-apples quantitative comparison with the 20 W run because the initial bowl amplitudes were very different and the 1 W test clipped the ADC.

However, the qualitative result is useful.

The 1 W configuration:

- easily achieves much greater vibration amplitude than required
- appears to allow substantially longer bowl sustain
- adds much less physical mass than the 20 W exciter
- requires only a tiny drive command

The experiment has therefore answered the main exciter-sizing question without requiring additional precise ringdown testing at this stage.

---

# 20 W vs 1 W Practical Conclusion

## 20 W exciter

Advantages:

- Extremely large power margin

Disadvantages:

- Far more power capability than required
- More physical mass attached to the bowl
- Greater potential mechanical damping
- Larger packaging requirement

## 1 W exciter

Advantages:

- More than enough drive capability
- Much lower mass
- Very strong sidewall coupling
- Tiny electrical drive level required
- Appears to interfere less with natural bowl sustain
- Better candidate for a multi-bowl product

Conclusion:

    20 W is substantially oversized.

    1 W is already more powerful than necessary for this test bowl.

It may eventually be possible to use an even smaller and lighter actuator if doing so reduces damping, cost, package size, or power requirements.

There is no immediate need to optimize below 1 W, however.

The 1 W exciter is a good current development platform.

---

# Closed-Loop Bowl Amplitude Control

A separate experiment demonstrated closed-loop control of bowl vibration amplitude.

Test conditions:

    Frequency:          528.700 Hz
    Target P2P:         220
    Initial DAC:        0.100%
    Maximum DAC:        0.500%
    Duration:           10 sec

The controller automatically adjusted DAC level based on Teensy piezo feedback.

Representative results:

    Time     DAC %      P2P
    ----     -----      ---
    0.7      0.1000     177
    1.5      0.1078     190.5
    2.2      0.1136     203
    3.7      0.1222     218
    4.4      0.1227     222
    5.9      0.1231     228
    7.4      0.1222     222.5
    8.8      0.1240     225

The system converged around:

    DAC amplitude: ~0.122%
    Bowl response: ~220 P2P

No ADC clipping occurred.

This proved that piezo feedback can regulate actual mechanical bowl amplitude rather than relying solely on commanded DAC amplitude.

This should eventually allow different bowls to maintain a desired acoustic/mechanical intensity despite different resonances, mounting efficiencies, and bowl characteristics.

---

# Smooth Sound-Bath Drive Experiment

The previous PCM5122 test architecture generated individual short WAV/tone segments.

This caused noticeable mechanical transitions when:

- starting a tone
- stopping a tone
- changing amplitude
- restarting the oscillator

These transitions are too aggressive for a natural sound-bath experience.

A new continuous-drive experiment was therefore created:

    tools/smooth_bowl_drive.py

The important changes are:

1. Continuous phase-running sine oscillator
2. Oscillator does not restart during amplitude changes
3. Smooth raised-cosine amplitude envelope
4. Zero envelope slope at the beginning and end of transitions
5. 32-bit PCM output rather than the earlier 16-bit test waveform

The 32-bit PCM path is particularly useful because the 1 W exciter requires extremely small amplitudes.

For comparison, with signed 16-bit audio:

    0.1% full scale ~= only 33 peak digital counts

The system now operates in a region where improved digital amplitude resolution is worthwhile.

---

# Smooth Drive Tests

Frequency:

    528.7 Hz

Peak drive:

    0.07%
    amplitude argument = 0.0007

Three envelopes were created.

## Gentle

    Attack:   8 sec
    Hold:     4 sec
    Release: 10 sec

Command:

    python tools/smooth_bowl_drive.py \
        --frequency 528.7 \
        --amplitude 0.0007 \
        --attack 8 \
        --hold 4 \
        --release 10

Result:

    Very smooth and subjectively pleasing.

The bowl emerges naturally instead of sounding like the actuator has been switched on.

---

## Faster

    Attack:   3 sec
    Hold:     4 sec
    Release:  5 sec

Command:

    python tools/smooth_bowl_drive.py \
        --frequency 528.7 \
        --amplitude 0.0007 \
        --attack 3 \
        --hold 4 \
        --release 5

This configuration is intended to test how fast the bowl can be modulated before the change becomes perceptually obvious or mechanically aggressive.

---

## Slow Sound-Bath Swell

    Attack:  15 sec
    Hold:    10 sec
    Release: 20 sec

Command:

    python tools/smooth_bowl_drive.py \
        --frequency 528.7 \
        --amplitude 0.0007 \
        --attack 15 \
        --hold 10 \
        --release 20

This is closer to the type of slow dynamic envelope expected during an automated sound bath.

---

# Saved Smooth-Drive Runner

The three smooth-drive tests are also saved in:

    run_smooth_bowl_drive_1W.sh

This provides an easy repeatable demonstration of the current 1 W configuration.

---

# Emerging Sound-Bath Architecture

The tests suggest that a realistic automated sound bath should NOT be constructed from discrete start/stop tones.

Instead, each active bowl should use a continuously running oscillator.

Conceptually:

    Continuous oscillator
             |
             v
      Smooth amplitude
          envelope
             |
             v
         PCM5122
             |
             v
         Amplifier
             |
             v
          Exciter
             |
             v
        Sound bowl

The amplitude envelope can then evolve slowly over seconds or tens of seconds.

Future sound-bath control can include:

- gradual fade-in/fade-out
- overlapping amplitude swells
- slow breathing-like intensity modulation
- alternating bowls
- two simultaneously active bowls
- smooth crossfades between bowls
- slight frequency adjustments around each bowl's resonance
- automatic resonance tracking
- closed-loop amplitude regulation using piezo feedback
- eventually biofeedback-driven changes to sound-bath behavior

The controller should avoid abrupt:

- oscillator starts
- oscillator stops
- phase resets
- large instantaneous gain changes

The goal should be for the listener to perceive the bowl itself evolving naturally rather than perceiving an electronic actuator controlling it.

---

# Current Conclusions

1. The piezo + Teensy sensing architecture is working well.

2. Automatic bowl resonance detection is working.

3. Resonance of the current bowl is consistently approximately 529 Hz.

4. Piezo peak-to-peak amplitude provides a useful mechanical intensity measurement.

5. Closed-loop amplitude regulation has been demonstrated.

6. Sidewall exciter mounting is dramatically better than the tested base mounting arrangements.

7. The 20 W exciter is far larger than necessary.

8. The 1 W exciter is already more powerful than necessary for this bowl.

9. Lower exciter mass appears desirable because the actuator itself can damp the bowl.

10. Continuous oscillator generation with slow smooth amplitude envelopes produces a much more natural result than discrete tone playback.

11. 32-bit PCM is appropriate because useful exciter drive levels are now extremely small fractions of full-scale DAC output.

12. The immediate development focus should move away from increasing actuator power and toward:

    - smooth musical control
    - repeatable mounting
    - multi-bowl operation
    - automatic resonance management
    - closed-loop bowl intensity
    - sound-bath sequencing

---

# Key Reference Values

Current bowl:

    Resonance: ~528.7-529.2 Hz

20 W sidewall:

    Drive:              0.150%
    Driven P2P:         ~220
    t50:                0.20 sec
    t37:                0.20 sec
    t20:                0.30 sec

1 W sidewall at approximately 5/8 height:

    Unclipped sweep:    0.130%
    Peak P2P:           281
    Resonance:          528.691 Hz

1 W strong ringdown test:

    Driven P2P:         821
    Initial ringdown:   830
    t50:                0.52 sec
    t37:                0.52 sec
    t20:                0.62 sec
    ADC clipped:        Yes

Smooth-drive demonstration:

    Frequency:          528.7 Hz
    Peak amplitude:     0.070%
    PCM:                32-bit / 48 kHz
    Envelope:           raised cosine

Current preferred exciter:

    1 W sidewall-mounted exciter
