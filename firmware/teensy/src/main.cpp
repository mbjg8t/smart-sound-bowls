#include <Arduino.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

constexpr uint32_t SAMPLE_RATE_HZ = 20000;
constexpr uint32_t SAMPLE_PERIOD_US = 1000000UL / SAMPLE_RATE_HZ;
constexpr uint32_t REPORT_MS = 100;

constexpr uint16_t MAX_SAMPLES = 2100;

// Frequency range we care about for bowl testing.
constexpr float MIN_FREQ_HZ = 150.0f;
constexpr float MAX_FREQ_HZ = 1200.0f;

// Don't try frequency detection on very weak signals.
constexpr uint16_t MIN_FREQ_P2P = 100;

// Detect the beginning of a new strike.
constexpr uint16_t STRIKE_P2P = 250;
constexpr uint16_t QUIET_P2P  = 100;

// Minimum normalized autocorrelation confidence.
constexpr float MIN_CONFIDENCE = 0.45f;

int adcPin = A0;
int adcNumber = 0;

uint32_t lastSampleUs = 0;
uint32_t lastReportMs = 0;

uint32_t sampleCount = 0;
uint64_t sampleSum = 0;
uint16_t sampleMin = 4095;
uint16_t sampleMax = 0;

uint16_t samples[MAX_SAMPLES];
uint16_t storedSamples = 0;

uint16_t previousP2P = 0;

// Automatic resonance voting.
//
// Each valid YIN result votes for a 5 Hz frequency bin.
// The sustained bowl resonance should accumulate far more votes
// than short-lived strike transients and secondary modes.

constexpr float VOTE_MIN_FREQ_HZ = 100.0f;
constexpr float VOTE_MAX_FREQ_HZ = 1200.0f;
constexpr float VOTE_BIN_HZ = 5.0f;

constexpr int VOTE_BIN_COUNT =
    (int)((VOTE_MAX_FREQ_HZ - VOTE_MIN_FREQ_HZ) / VOTE_BIN_HZ) + 1;

float frequencyVotes[VOTE_BIN_COUNT];
uint16_t frequencyHits[VOTE_BIN_COUNT];

uint16_t totalFrequencyVotes = 0;

float detectedFrequency = 0.0f;
float detectedScore = 0.0f;
uint16_t detectedHits = 0;

// Don't call anything "detected" until enough ring-down evidence exists.
constexpr uint16_t MIN_TOTAL_VOTES = 5;
constexpr uint16_t MIN_WINNING_HITS = 3;

// Winner should be meaningfully stronger than the runner-up.
constexpr float WINNER_RATIO = 1.35f;

char commandBuffer[32];
uint8_t commandLength = 0;

// Forward declaration
void resetFrequencyLock();

void resetStats()
{
    sampleCount = 0;
    sampleSum = 0;
    sampleMin = 4095;
    sampleMax = 0;
    storedSamples = 0;
}

int analogPinFromNumber(int n)
{
    switch (n)
    {
        case 0:  return A0;
        case 1:  return A1;
        case 2:  return A2;
        case 3:  return A3;
        case 4:  return A4;
        case 5:  return A5;
        case 6:  return A6;
        case 7:  return A7;
        case 8:  return A8;
        case 9:  return A9;
        case 10: return A10;
        case 11: return A11;
        case 12: return A12;
        case 13: return A13;
        default: return -1;
    }
}

void selectAnalogPin(int n)
{
    int pin = analogPinFromNumber(n);

    if (pin < 0)
    {
        Serial.print("Invalid analog input: A");
        Serial.println(n);
        return;
    }

    adcNumber = n;
    adcPin = pin;

    previousP2P = 0;
    resetFrequencyLock();
    resetStats();

    Serial.print("Selected A");
    Serial.print(adcNumber);
    Serial.print(" (digital pin ");
    Serial.print(adcPin);
    Serial.println(")");
}

/*
 * Normalized autocorrelation.
 *
 * We subtract the measured mean so the ~195-count DC offset from the
 * piezo board does not affect frequency detection.
 *
 * For every possible lag corresponding to 150-1200 Hz, calculate:
 *
 *        sum(x[n] * x[n+lag])
 *   --------------------------------
 *   sqrt(sum(x[n]^2) * sum(x[n+lag]^2))
 *
 * Perfect repeating waveform approaches 1.0.
 */
float calculateFrequency(float mean, uint16_t p2p, float &confidence)
{
    confidence = 0.0f;

    if (storedSamples < 200)
        return 0.0f;

    if (p2p < MIN_FREQ_P2P)
        return 0.0f;

    int minLag = (int)(SAMPLE_RATE_HZ / MAX_FREQ_HZ);
    int maxLag = (int)(SAMPLE_RATE_HZ / MIN_FREQ_HZ);

    if (minLag < 2)
        minLag = 2;

    if (maxLag >= storedSamples / 2)
        maxLag = storedSamples / 2;

    static float yin[MAX_SAMPLES / 2];

    yin[0] = 1.0f;

    /*
     * YIN difference function:
     *
     * d(tau) = sum (x[i] - x[i+tau])^2
     *
     * We don't actually need to subtract the DC mean here because
     * the subtraction occurs between the two samples.
     */
    for (int tau = 1; tau <= maxLag; tau++)
    {
        uint64_t sum = 0;

        int count = storedSamples - tau;

        for (int i = 0; i < count; i++)
        {
            int32_t delta =
                (int32_t)samples[i] -
                (int32_t)samples[i + tau];

            sum += (uint64_t)((int64_t)delta * delta);
        }

        yin[tau] = (float)sum;
    }

    /*
     * Cumulative Mean Normalized Difference Function.
     *
     * Periodic matches approach zero.
     */
    float runningSum = 0.0f;

    for (int tau = 1; tau <= maxLag; tau++)
    {
        runningSum += yin[tau];

        if (runningSum > 0.0f)
            yin[tau] *= (float)tau / runningSum;
        else
            yin[tau] = 1.0f;
    }

    /*
     * Typical YIN threshold is around 0.10-0.20.
     * 0.20 is deliberately forgiving for our clipped piezo signal.
     */
    constexpr float YIN_THRESHOLD = 0.20f;

    int bestTau = -1;

    for (int tau = minLag; tau <= maxLag; tau++)
    {
        if (yin[tau] < YIN_THRESHOLD)
        {
            /*
             * Once we cross the threshold, continue downhill to
             * the local minimum.
             */
            while (tau + 1 <= maxLag &&
                   yin[tau + 1] < yin[tau])
            {
                tau++;
            }

            bestTau = tau;
            break;
        }
    }

    /*
     * If nothing crossed our threshold, use the best minimum,
     * but reject it later if confidence is poor.
     */
    if (bestTau < 0)
    {
        float bestValue = 1.0f;

        for (int tau = minLag; tau <= maxLag; tau++)
        {
            if (yin[tau] < bestValue)
            {
                bestValue = yin[tau];
                bestTau = tau;
            }
        }
    }

    if (bestTau <= minLag || bestTau >= maxLag)
        return 0.0f;

    confidence = 1.0f - yin[bestTau];

    if (confidence < MIN_CONFIDENCE)
        return 0.0f;

    /*
     * Parabolic interpolation around the YIN minimum.
     *
     * This gives us a fractional sample period instead of being
     * limited to exactly 37, 38, 39 samples, etc.
     */
    float y0 = yin[bestTau - 1];
    float y1 = yin[bestTau];
    float y2 = yin[bestTau + 1];

    float denominator = y0 - 2.0f * y1 + y2;

    float betterTau = (float)bestTau;

    if (fabsf(denominator) > 0.000001f)
    {
        float offset =
            0.5f * (y0 - y2) / denominator;

        if (offset > -1.0f && offset < 1.0f)
            betterTau += offset;
    }

    if (betterTau <= 0.0f)
        return 0.0f;

    return (float)SAMPLE_RATE_HZ / betterTau;
}



void resetFrequencyLock()
{
    for (int i = 0; i < VOTE_BIN_COUNT; i++)
    {
        frequencyVotes[i] = 0.0f;
        frequencyHits[i] = 0;
    }

    totalFrequencyVotes = 0;

    detectedFrequency = 0.0f;
    detectedScore = 0.0f;
    detectedHits = 0;
}

float updateFrequencyLock(float rawFrequency, float confidence)
{
    if (rawFrequency <= 0.0f)
        return 0.0f;

    if (confidence < MIN_CONFIDENCE)
        return 0.0f;

    if (rawFrequency < VOTE_MIN_FREQ_HZ ||
        rawFrequency > VOTE_MAX_FREQ_HZ)
        return 0.0f;

    /*
     * Round to nearest 5 Hz bin.
     *
     * Examples:
     *
     *   528.8 -> 530 Hz
     *   529.7 -> 530 Hz
     *   531.1 -> 530 Hz
     *
     * This is deliberate: we're discovering the resonance cluster,
     * not trying to preserve sub-Hz precision in the voting stage.
     */
    int bin =
        (int)(((rawFrequency - VOTE_MIN_FREQ_HZ) /
               VOTE_BIN_HZ) + 0.5f);

    if (bin < 0 || bin >= VOTE_BIN_COUNT)
        return 0.0f;

    /*
     * Confidence-weighted vote.
     *
     * Persistence matters most:
     * every 100 ms window contributes one vote, so a sustained
     * resonance naturally beats a short strike transient.
     */
    frequencyVotes[bin] += confidence;
    frequencyHits[bin]++;
    totalFrequencyVotes++;

    int bestBin = -1;
    int secondBin = -1;

    float bestScore = 0.0f;
    float secondScore = 0.0f;

    for (int i = 0; i < VOTE_BIN_COUNT; i++)
    {
        float score = frequencyVotes[i];

        if (score > bestScore)
        {
            secondScore = bestScore;
            secondBin = bestBin;

            bestScore = score;
            bestBin = i;
        }
        else if (score > secondScore)
        {
            secondScore = score;
            secondBin = i;
        }
    }

    detectedFrequency = 0.0f;
    detectedScore = 0.0f;
    detectedHits = 0;

    if (bestBin < 0)
        return 0.0f;

    uint16_t bestHits = frequencyHits[bestBin];

    /*
     * Wait until we've observed enough of the decay before declaring
     * a winner.
     */
    if (totalFrequencyVotes < MIN_TOTAL_VOTES)
        return 0.0f;

    if (bestHits < MIN_WINNING_HITS)
        return 0.0f;

    /*
     * Require separation from the runner-up.
     *
     * If there is essentially no runner-up, the winner is accepted.
     */
    if (secondScore > 0.0f)
    {
        float ratio = bestScore / secondScore;

        if (ratio < WINNER_RATIO)
            return 0.0f;
    }

    detectedFrequency =
        VOTE_MIN_FREQ_HZ +
        ((float)bestBin * VOTE_BIN_HZ);

    detectedScore = bestScore;
    detectedHits = bestHits;

    return detectedFrequency;
}


void processCommand(char *cmd)
{
    while (*cmd == ' ' || *cmd == '\t')
        cmd++;

    Serial.print("Command received: [");
    Serial.print(cmd);
    Serial.println("]");

    if (strcmp(cmd, "?") == 0 || strcasecmp(cmd, "help") == 0)
    {
        Serial.println();
        Serial.println("Available ADC inputs:");
        Serial.println("  A0   pin 14");
        Serial.println("  A1   pin 15");
        Serial.println("  A2   pin 16");
        Serial.println("  A3   pin 17");
        Serial.println("  A4   pin 18");
        Serial.println("  A5   pin 19");
        Serial.println("  A6   pin 20");
        Serial.println("  A7   pin 21");
        Serial.println("  A8   pin 22");
        Serial.println("  A9   pin 23");
        Serial.println("  A10");
        Serial.println("  A11");
        Serial.println("  A12");
        Serial.println("  A13");
        Serial.println();
        return;
    }

    if (toupper(cmd[0]) == 'A' && isdigit(cmd[1]))
    {
        int n = atoi(cmd + 1);
        selectAnalogPin(n);
        return;
    }

    Serial.print("Unknown command: ");
    Serial.println(cmd);
}

void readSerialCommands()
{
    while (Serial.available())
    {
        char c = Serial.read();

        if (c == '\r')
            continue;

        if (c == '\n')
        {
            commandBuffer[commandLength] = '\0';

            if (commandLength > 0)
                processCommand(commandBuffer);

            commandLength = 0;
        }
        else if (commandLength < sizeof(commandBuffer) - 1)
        {
            commandBuffer[commandLength++] = c;
        }
    }
}

void setup()
{
    Serial.begin(115200);
    analogReadResolution(12);

    selectAnalogPin(0);

    delay(500);

    Serial.println();
    Serial.println("TEENSY PIEZO AUTOCORRELATION TEST");
    Serial.println("---------------------------------");

    Serial.print("Sample rate: ");
    Serial.print(SAMPLE_RATE_HZ);
    Serial.println(" Hz");

    Serial.print("Frequency range: ");
    Serial.print(MIN_FREQ_HZ, 0);
    Serial.print("-");
    Serial.print(MAX_FREQ_HZ, 0);
    Serial.println(" Hz");

    Serial.println();

    lastSampleUs = micros();
    lastReportMs = millis();

    resetStats();
}

void loop()
{
    readSerialCommands();

    uint32_t nowUs = micros();

    if ((uint32_t)(nowUs - lastSampleUs) >= SAMPLE_PERIOD_US)
    {
        lastSampleUs += SAMPLE_PERIOD_US;

        uint16_t value = analogRead(adcPin);

        if (value < sampleMin)
            sampleMin = value;

        if (value > sampleMax)
            sampleMax = value;

        sampleSum += value;
        sampleCount++;

        if (storedSamples < MAX_SAMPLES)
            samples[storedSamples++] = value;
    }

    uint32_t nowMs = millis();

    if ((uint32_t)(nowMs - lastReportMs) >= REPORT_MS)
    {
        lastReportMs += REPORT_MS;

        if (sampleCount > 0)
        {
            float mean = (float)sampleSum / sampleCount;
            uint16_t p2p = sampleMax - sampleMin;

            bool newStrike =
                previousP2P < QUIET_P2P &&
                p2p >= STRIKE_P2P;

            float confidence = 0.0f;
            float frequency = 0.0f;

            if (newStrike)
            {
                resetFrequencyLock();
            }
            else
            {
                frequency = calculateFrequency(mean, p2p, confidence);
            }

            float stableFrequency =
                updateFrequencyLock(frequency, confidence);

            Serial.print("A");
            Serial.print(adcNumber);

            Serial.print(" n=");
            Serial.print(sampleCount);

            Serial.print(" min=");
            Serial.print(sampleMin);

            Serial.print(" max=");
            Serial.print(sampleMax);

            Serial.print(" mean=");
            Serial.print(mean, 1);

            Serial.print(" p2p=");
            Serial.print(p2p);

            Serial.print(" freq=");

            if (newStrike)
            {
                Serial.print("--- STRIKE");
            }
            else if (frequency > 0.0f)
            {
                Serial.print(frequency, 1);
                Serial.print("Hz");

                Serial.print(" conf=");
                Serial.print(confidence, 2);

                Serial.print(" detect=");

                if (stableFrequency > 0.0f)
                {
                    Serial.print(stableFrequency, 1);
                    Serial.print("Hz");

                    Serial.print(" hits=");
                    Serial.print(detectedHits);

                    Serial.print(" score=");
                    Serial.print(detectedScore, 1);
                }
                else
                {
                    Serial.print("---");

                    Serial.print(" votes=");
                    Serial.print(totalFrequencyVotes);
                }
            }
            else
            {
                Serial.print("---");

                if (detectedFrequency > 0.0f)
                {
                    Serial.print(" detect=");
                    Serial.print(detectedFrequency, 1);
                    Serial.print("Hz");
                }
            }

            Serial.println();

            previousP2P = p2p;
        }

        resetStats();
    }
}
