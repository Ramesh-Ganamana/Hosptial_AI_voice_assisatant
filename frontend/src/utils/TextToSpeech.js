/**
 * TextToSpeech - Converts text to speech using browser's Web Speech API
 */
class TextToSpeech {
  constructor() {
    this.synth = window.speechSynthesis;
    this.currentUtterance = null;
    this.isSpeaking = false;
    this.voices = [];
    
    // Load voices
    this.loadVoices();
    
    // Voices might load asynchronously
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = () => {
        this.loadVoices();
      };
    }
  }
  
  loadVoices() {
    this.voices = this.synth.getVoices();
    console.log('Available voices:', this.voices.length);
  }
  
  /**
   * Select the best voice for Indian English
   */
  selectVoice() {
    // Try to find Indian English voice
    let voice = this.voices.find(v => 
      v.lang.includes('en-IN') || v.name.includes('Indian')
    );
    
    // Fallback to British English (closer to Indian accent)
    if (!voice) {
      voice = this.voices.find(v => v.lang.includes('en-GB'));
    }
    
    // Fallback to US English
    if (!voice) {
      voice = this.voices.find(v => v.lang.includes('en-US'));
    }
    
    // Fallback to any English voice
    if (!voice) {
      voice = this.voices.find(v => v.lang.startsWith('en'));
    }
    
    // Fallback to first voice
    if (!voice) {
      voice = this.voices[0];
    }
    
    return voice;
  }
  
  /**
   * Speak the given text
   */
  speak(text, options = {}) {
    return new Promise((resolve, reject) => {
      try {
        // Cancel any ongoing speech
        this.stop();
        
        if (!text || text.trim() === '') {
          resolve();
          return;
        }
        
        // Create utterance
        this.currentUtterance = new SpeechSynthesisUtterance(text);
        
        // Select voice
        const voice = this.selectVoice();
        if (voice) {
          this.currentUtterance.voice = voice;
        }
        
        // Set properties
        this.currentUtterance.rate = options.rate || 1.0;   // Speed (0.1 to 10)
        this.currentUtterance.pitch = options.pitch || 1.0; // Pitch (0 to 2)
        this.currentUtterance.volume = options.volume || 1.0; // Volume (0 to 1)
        
        // Event handlers
        this.currentUtterance.onstart = () => {
          this.isSpeaking = true;
          console.log('Started speaking:', text.substring(0, 50) + '...');
          if (options.onStart) options.onStart();
        };
        
        this.currentUtterance.onend = () => {
          this.isSpeaking = false;
          console.log('Finished speaking');
          if (options.onEnd) options.onEnd();
          resolve();
        };
        
        this.currentUtterance.onerror = (event) => {
          this.isSpeaking = false;
          console.error('Speech error:', event.error);
          if (options.onError) options.onError(event);
          reject(event.error);
        };
        
        // Speak
        this.synth.speak(this.currentUtterance);
        
      } catch (error) {
        console.error('Error in speak():', error);
        reject(error);
      }
    });
  }
  
  /**
   * Stop speaking
   */
  stop() {
    if (this.synth.speaking) {
      this.synth.cancel();
      this.isSpeaking = false;
      console.log('Speech cancelled');
    }
  }
  
  /**
   * Pause speaking
   */
  pause() {
    if (this.synth.speaking && !this.synth.paused) {
      this.synth.pause();
      console.log('Speech paused');
    }
  }
  
  /**
   * Resume speaking
   */
  resume() {
    if (this.synth.paused) {
      this.synth.resume();
      console.log('Speech resumed');
    }
  }
  
  /**
   * Check if currently speaking
   */
  isCurrentlySpeaking() {
    return this.isSpeaking || this.synth.speaking;
  }
  
  /**
   * Get available voices
   */
  getVoices() {
    return this.voices;
  }
}

export default TextToSpeech;
