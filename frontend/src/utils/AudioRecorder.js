/**
 * AudioRecorder - Records audio from microphone and converts to WAV format for Vosk
 */
class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
    this.audioContext = null;
    this.analyser = null;
    this.silenceDetectionInterval = null;
    this.silenceCallback = null;
  }

  async start() {
    try {
      // Request microphone access
      this.stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        } 
      });

      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      // Start recording
      this.mediaRecorder.start(100); // Collect data every 100ms

      // Setup silence detection
      this.setupSilenceDetection();

      return true;
    } catch (error) {
      console.error('Error starting audio recording:', error);
      throw error;
    }
  }

  setupSilenceDetection() {
    // Create audio context for silence detection
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    source.connect(this.analyser);

    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    let silenceStart = null;
    const SILENCE_THRESHOLD = 25; // Threshold for detecting silence (higher = more sensitive)
    const SILENCE_DURATION = 5000; // 5 seconds of CONTINUOUS silence
    const CHECK_INTERVAL = 100; // Check every 100ms

    this.silenceDetectionInterval = setInterval(() => {
      this.analyser.getByteTimeDomainData(dataArray);

      // Calculate average audio level
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        const value = Math.abs(dataArray[i] - 128);
        sum += value;
      }
      const average = sum / bufferLength;

      // Check if user is speaking or silent
      if (average < SILENCE_THRESHOLD) {
        // Silent - start or continue counting
        if (!silenceStart) {
          silenceStart = Date.now();
          console.log('Silence detected, starting timer...');
        } else {
          const silenceDuration = Date.now() - silenceStart;
          if (silenceDuration > SILENCE_DURATION) {
            // CONTINUOUS silence for 5 seconds - auto-stop
            console.log(`Auto-stopping: ${silenceDuration}ms of continuous silence`);
            if (this.silenceCallback) {
              this.silenceCallback();
            }
          }
        }
      } else {
        // User is speaking - RESET the silence timer
        if (silenceStart) {
          console.log('Voice detected, resetting silence timer');
        }
        silenceStart = null; // Reset timer when voice detected
      }
    }, CHECK_INTERVAL);
  }

  onSilenceDetected(callback) {
    this.silenceCallback = callback;
  }

  async stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = async () => {
        // Stop silence detection
        if (this.silenceDetectionInterval) {
          clearInterval(this.silenceDetectionInterval);
          this.silenceDetectionInterval = null;
        }

        if (this.audioContext) {
          this.audioContext.close();
          this.audioContext = null;
        }

        // Stop all tracks
        if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
        }

        // Convert to WAV
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        const wavBlob = await this.convertToWav(audioBlob);
        resolve(wavBlob);
      };

      this.mediaRecorder.stop();
    });
  }

  async convertToWav(blob) {
    try {
      // Create audio context
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuffer = await blob.arrayBuffer();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      // Convert to mono 16kHz
      const offlineContext = new OfflineAudioContext(
        1, // mono
        audioBuffer.duration * 16000,
        16000 // 16kHz sample rate
      );

      const source = offlineContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(offlineContext.destination);
      source.start();

      const renderedBuffer = await offlineContext.startRendering();

      // Convert to WAV format
      const wavData = this.audioBufferToWav(renderedBuffer);
      return new Blob([wavData], { type: 'audio/wav' });
    } catch (error) {
      console.error('Error converting to WAV:', error);
      throw error;
    }
  }

  audioBufferToWav(buffer) {
    const numChannels = 1;
    const sampleRate = buffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const channelData = buffer.getChannelData(0);
    const samples = new Int16Array(channelData.length);

    // Convert float samples to 16-bit PCM
    for (let i = 0; i < channelData.length; i++) {
      const s = Math.max(-1, Math.min(1, channelData[i]));
      samples[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    const dataLength = samples.length * 2;
    const buffer_new = new ArrayBuffer(44 + dataLength);
    const view = new DataView(buffer_new);

    // WAV header
    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * (bitDepth / 8), true);
    view.setUint16(32, numChannels * (bitDepth / 8), true);
    view.setUint16(34, bitDepth, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    // Write PCM samples
    const offset = 44;
    for (let i = 0; i < samples.length; i++) {
      view.setInt16(offset + i * 2, samples[i], true);
    }

    return buffer_new;
  }

  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  isRecording() {
    return this.mediaRecorder && this.mediaRecorder.state === 'recording';
  }
}

export default AudioRecorder;