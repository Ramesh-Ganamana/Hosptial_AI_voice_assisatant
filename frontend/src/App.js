import { useState, useEffect, useRef } from "react";
import "@/App.css";
import axios from "axios";
import AudioRecorder from "@/utils/AudioRecorder";
import TextToSpeech from "@/utils/TextToSpeech";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Mic, Square, Loader2, AlertCircle, Hospital, Volume2, VolumeX } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [conversation, setConversation] = useState([]);
  const [permissionState, setPermissionState] = useState("prompt"); // prompt, granted, denied
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [autoSpeak, setAutoSpeak] = useState(true); // Auto-speak AI responses
  const [isSpeaking, setIsSpeaking] = useState(false);
  
  const audioRecorderRef = useRef(null);
  const ttsRef = useRef(null);
  const conversationEndRef = useRef(null);

  useEffect(() => {
    // Generate session ID
    setSessionId(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
    
    // Initialize Text-to-Speech
    ttsRef.current = new TextToSpeech();
    
    // Check microphone permission status
    checkMicrophonePermission();
  }, []);

  useEffect(() => {
    // Scroll to bottom of conversation
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversation]);

  const checkMicrophonePermission = async () => {
    try {
      if (navigator.permissions && navigator.permissions.query) {
        const result = await navigator.permissions.query({ name: "microphone" });
        setPermissionState(result.state);
        
        result.addEventListener("change", () => {
          setPermissionState(result.state);
        });
      }
    } catch (err) {
      console.log("Permission API not supported, will request on use");
    }
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      await stopRecording();
    } else {
      // Start recording
      await startRecording();
    }
  };

  const startRecording = async () => {
    try {
      setError(null);
      setIsRecording(true);

      // Create new audio recorder
      audioRecorderRef.current = new AudioRecorder();

      // Setup silence detection
      audioRecorderRef.current.onSilenceDetected(() => {
        console.log("Silence detected, stopping recording");
        stopRecording();
      });

      // Start recording
      await audioRecorderRef.current.start();
      setPermissionState("granted");

    } catch (err) {
      console.error("Error starting recording:", err);
      setIsRecording(false);
      
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setPermissionState("denied");
        setError("Microphone access denied. Please allow microphone access to use voice features.");
      } else {
        setError("Failed to start recording. Please check your microphone.");
      }
    }
  };

  const stopRecording = async () => {
    try {
      if (!audioRecorderRef.current) return;

      setIsRecording(false);
      setIsProcessing(true);

      // Stop recording and get audio blob
      const audioBlob = await audioRecorderRef.current.stop();
      
      if (!audioBlob || audioBlob.size === 0) {
        setIsProcessing(false);
        setError("No audio recorded. Please try again.");
        return;
      }

      // Send audio to backend
      await sendAudioToBackend(audioBlob);

    } catch (err) {
      console.error("Error stopping recording:", err);
      setError("Failed to process recording. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  const sendAudioToBackend = async (audioBlob) => {
    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "audio.wav");
      
      if (sessionId) {
        formData.append("session_id", sessionId);
      }

      const response = await axios.post(`${API}/process-audio?session_id=${sessionId}`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const { transcription, response: aiResponse } = response.data;

      // Add to conversation
      if (transcription && transcription.trim()) {
        setConversation(prev => [
          ...prev,
          { type: "user", text: transcription },
          { type: "assistant", text: aiResponse }
        ]);
        
        // Auto-speak the AI response if enabled
        if (autoSpeak && aiResponse) {
          speakText(aiResponse);
        }
      } else {
        setError("Couldn't understand the audio. Please speak clearly and try again.");
      }

    } catch (err) {
      console.error("Error sending audio to backend:", err);
      setError("Failed to process your request. Please try again.");
    }
  };

  const enableMicrophone = () => {
    // Guide user to enable microphone
    setError(
      "To enable microphone: Click the 🔒 or ⓘ icon in your browser's address bar, then allow microphone access."
    );
  };

  const speakText = async (text) => {
    try {
      setIsSpeaking(true);
      await ttsRef.current.speak(text, {
        rate: 1.0,
        pitch: 1.0,
        volume: 1.0,
        onEnd: () => setIsSpeaking(false),
        onError: () => setIsSpeaking(false)
      });
    } catch (error) {
      console.error("Error speaking text:", error);
      setIsSpeaking(false);
    }
  };

  const stopSpeaking = () => {
    if (ttsRef.current) {
      ttsRef.current.stop();
      setIsSpeaking(false);
    }
  };

  const toggleAutoSpeak = () => {
    setAutoSpeak(!autoSpeak);
    // Stop any ongoing speech when disabling
    if (autoSpeak && isSpeaking) {
      stopSpeaking();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <Hospital className="w-12 h-12 text-blue-600 mr-3" />
            <h1 className="text-4xl font-bold text-gray-800">Hospital AI Assistant</h1>
          </div>
          <p className="text-gray-600">
            Speak naturally to check doctor availability and book appointments
          </p>
          
          {/* TTS Toggle */}
          <div className="flex items-center justify-center mt-4 gap-2">
            <Button
              onClick={toggleAutoSpeak}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              {autoSpeak ? (
                <>
                  <Volume2 className="w-4 h-4" />
                  Voice Responses ON
                </>
              ) : (
                <>
                  <VolumeX className="w-4 h-4" />
                  Voice Responses OFF
                </>
              )}
            </Button>
            {isSpeaking && (
              <Button
                onClick={stopSpeaking}
                variant="destructive"
                size="sm"
              >
                Stop Speaking
              </Button>
            )}
          </div>
        </div>

        {/* Main Card */}
        <Card className="shadow-xl">
          
          {/* Conversation Area */}
          <div className="p-6 min-h-[400px] max-h-[500px] overflow-y-auto bg-gray-50">
            {conversation.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <Mic className="w-16 h-16 text-gray-300 mb-4" />
                <h2 className="text-xl font-semibold text-gray-700 mb-2">
                  Welcome! How can I help you today?
                </h2>
                <p className="text-gray-500 max-w-md">
                  Click the Speak button below and ask about:<br />
                  • Doctor availability by specialty<br />
                  • Booking an appointment<br />
                  • Hospital services
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {conversation.map((message, index) => (
                  <div
                    key={index}
                    className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] p-4 rounded-lg ${
                        message.type === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-white text-gray-800 border border-gray-200"
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {message.type === "assistant" && autoSpeak && (
                          <Volume2 className="w-4 h-4 mt-1 flex-shrink-0 text-blue-600" />
                        )}
                        <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={conversationEndRef} />
              </div>
            )}
          </div>

          {/* Error Display */}
          {error && (
            <div className="px-6 py-3 border-t border-gray-200">
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            </div>
          )}

          {/* Controls */}
          <div className="p-6 bg-white border-t border-gray-200">
            <div className="flex flex-col items-center space-y-4">
              
              {/* Recording Status */}
              {(isRecording || isProcessing) && (
                <div className="text-center">
                  {isRecording && (
                    <div className="flex items-center text-red-600 animate-pulse">
                      <div className="w-3 h-3 bg-red-600 rounded-full mr-2"></div>
                      <span className="font-medium">Listening... (speak now)</span>
                    </div>
                  )}
                  {isProcessing && (
                    <div className="flex items-center text-blue-600">
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      <span className="font-medium">Processing...</span>
                    </div>
                  )}
                </div>
              )}

              {/* Main Button */}
              {permissionState === "denied" ? (
                <div className="text-center space-y-3">
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Microphone access is blocked. Please enable it in your browser settings.
                    </AlertDescription>
                  </Alert>
                  <Button onClick={enableMicrophone} variant="outline">
                    How to Enable Microphone
                  </Button>
                </div>
              ) : (
                <Button
                  onClick={handleToggleRecording}
                  disabled={isProcessing}
                  size="lg"
                  className={`px-8 py-6 text-lg font-semibold transition-all ${
                    isRecording
                      ? "bg-red-600 hover:bg-red-700"
                      : "bg-blue-600 hover:bg-blue-700"
                  }`}
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Processing...
                    </>
                  ) : isRecording ? (
                    <>
                      <Square className="w-5 h-5 mr-2" />
                      Stop
                    </>
                  ) : (
                    <>
                      <Mic className="w-5 h-5 mr-2" />
                      Speak
                    </>
                  )}
                </Button>
              )}

              {/* Hint Text */}
              {!isRecording && !isProcessing && permissionState !== "denied" && (
                <div className="text-center space-y-1">
                  <p className="text-sm font-semibold text-gray-700">
                    Auto-stops after 10 seconds of complete silence
                  </p>
                  <p className="text-xs text-blue-600 font-medium">
                    👉 Use "Stop" button anytime to finish speaking
                  </p>
                  {autoSpeak && (
                    <p className="text-xs text-blue-600 flex items-center justify-center gap-1">
                      <Volume2 className="w-3 h-3" />
                      AI will speak responses back to you
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Footer */}
        <div className="text-center mt-6 text-sm text-gray-500">
          <p>Powered by AI • Voice-First Interface</p>
        </div>
      </div>
    </div>
  );
}

export default App;
