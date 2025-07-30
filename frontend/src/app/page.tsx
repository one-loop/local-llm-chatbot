"use client"
import React, { useState, useRef, useEffect } from "react";
import styles from "./page.module.css";
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';  // Add this import at the top

// Chat message type
interface Message {
  sender: "user" | "bot";
  text: string;
}

// MascotEyes component: SVG mascot with eyes that follow the cursor
function MascotEyes() {
  // Eye center positions (relative to SVG viewBox)
  const leftEyeOrigin = { x: 129.5, y: 118 };
  const rightEyeOrigin = { x: 198.5, y: 118 };
  // How far the eyes can move from their origin
  const maxOffset = 7;
  const [eyeOffset, setEyeOffset] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    function handleMouseMove(e: MouseEvent) {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      // SVG center (bubble center)
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      // Vector from center to mouse
      const dx = e.clientX - centerX;
      const dy = e.clientY - centerY;
      // Normalize and scale to maxOffset
      const dist = Math.sqrt(dx * dx + dy * dy);
      const scale = dist > 0 ? Math.min(maxOffset, dist) / dist : 0;
      setEyeOffset({ x: dx * scale, y: dy * scale });
    }
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <svg
      ref={svgRef}
      width="80" height="80" viewBox="0 0 328 286"
      style={{marginRight: 'auto', marginLeft: 'auto', marginBottom: 30, display: 'block'}}
      fill="none" xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M261.768 238.869L212.482 225.691L248.59 189.583L261.768 238.869Z" fill="url(#paint0_linear_15_19)"/>
      <path d="M265 138C265 193.228 220.228 238 165 238C109.772 238 65 193.228 65 138C65 82.7715 109.772 38 165 38C220.228 38 265 82.7715 265 138Z" fill="url(#paint1_linear_15_19)"/>
      <path d="M0 118C0 109.163 7.16344 102 16 102H30C38.8366 102 46 109.163 46 118V163C46 171.837 38.8366 179 30 179H16C7.16344 179 0 171.837 0 163V118Z" fill="url(#paint2_linear_15_19)"/>
      <path d="M282 119C282 110.163 289.163 103 298 103H312C320.837 103 328 110.163 328 119V164C328 172.837 320.837 180 312 180H298C289.163 180 282 172.837 282 164V119Z" fill="url(#paint3_linear_15_19)"/>
      <path d="M164.5 0C240.439 0 302 61.5608 302 137.5C302 152.332 299.652 166.616 295.307 180H274.076C279.192 166.82 282 152.488 282 137.5C282 72.6065 229.393 20 164.5 20C99.6065 20 47 72.6065 47 137.5C47 202.393 99.6065 255 164.5 255C167.019 255 169.52 254.92 172 254.764V274.797C169.517 274.93 167.016 275 164.5 275C88.5608 275 27 213.439 27 137.5C27 61.5608 88.5608 0 164.5 0Z" fill="url(#paint4_linear_15_19)"/>
      <path d="M182 268C182 277.941 173.941 286 164 286C154.059 286 146 277.941 146 268C146 258.059 154.059 250 164 250C173.941 250 182 258.059 182 268Z" fill="url(#paint5_linear_15_19)"/>
      {/* Eyes (rectangles) */}
      <rect x={121 + eyeOffset.x * 1.5} y={84 + eyeOffset.y * 1.5} width="17" height="68" rx="8.5" fill="#141414"/>
      <rect x={190 + eyeOffset.x * 1.5} y={84 + eyeOffset.y * 1.5} width="17" height="68" rx="8.5" fill="#141414"/>
      <defs>
        <linearGradient id="paint0_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint1_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint2_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint3_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint4_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint5_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

// Add a new MascotEyesSmall component for the 32x32 icon
function MascotEyesSmall() {
  // Use the same MascotEyes SVG but fixed at 32x32 and eyes centered (no movement)
  return (
    <svg width="32" height="32" viewBox="0 0 328 286" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M261.768 238.869L212.482 225.691L248.59 189.583L261.768 238.869Z" fill="url(#paint0_linear_15_19)"/>
      <path d="M265 138C265 193.228 220.228 238 165 238C109.772 238 65 193.228 65 138C65 82.7715 109.772 38 165 38C220.228 38 265 82.7715 265 138Z" fill="url(#paint1_linear_15_19)"/>
      <path d="M0 118C0 109.163 7.16344 102 16 102H30C38.8366 102 46 109.163 46 118V163C46 171.837 38.8366 179 30 179H16C7.16344 179 0 171.837 0 163V118Z" fill="url(#paint2_linear_15_19)"/>
      <path d="M282 119C282 110.163 289.163 103 298 103H312C320.837 103 328 110.163 328 119V164C328 172.837 320.837 180 312 180H298C289.163 180 282 172.837 282 164V119Z" fill="url(#paint3_linear_15_19)"/>
      <path d="M164.5 0C240.439 0 302 61.5608 302 137.5C302 152.332 299.652 166.616 295.307 180H274.076C279.192 166.82 282 152.488 282 137.5C282 72.6065 229.393 20 164.5 20C99.6065 20 47 72.6065 47 137.5C47 202.393 99.6065 255 164.5 255C167.019 255 169.52 254.92 172 254.764V274.797C169.517 274.93 167.016 275 164.5 275C88.5608 275 27 213.439 27 137.5C27 61.5608 88.5608 0 164.5 0Z" fill="url(#paint4_linear_15_19)"/>
      <path d="M182 268C182 277.941 173.941 286 164 286C154.059 286 146 277.941 146 268C146 258.059 154.059 250 164 250C173.941 250 182 258.059 182 268Z" fill="url(#paint5_linear_15_19)"/>
      {/* Eyes (rectangles) centered */}
      <rect x={121} y={84} width="17" height="68" rx="8.5" fill="#141414"/>
      <rect x={190} y={84} width="17" height="68" rx="8.5" fill="#141414"/>
      <defs>
        <linearGradient id="paint0_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint1_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint2_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint3_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint4_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
        <linearGradient id="paint5_linear_15_19" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
          <stop stopColor="white"/>
          <stop offset="1" stopColor="#999999"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [centered, setCentered] = useState(true); // Fix: add this line
  const [showTyping, setShowTyping] = useState(false); // Typing indicator
  const [stoppedMessages, setStoppedMessages] = useState<Set<number>>(new Set()); // Track stopped messages
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);

  useEffect(() => {
    // Warm up the backend model on page load
    fetch('http://localhost:5000/warmup').catch(() => {});
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const sendMessage = async (overrideInput?: string) => {
    const chatList = document.querySelector('.chat-message-list') as HTMLElement | null;
    if (chatList) chatList.style.justifyContent = 'flex-start'; // Reset justify content to flex-start
    // scroll to the bottom of the chat list
    if (chatList) chatList.style.height += '500px';
    chatList?.scrollTo({
      top: chatList.scrollHeight,
      behavior: "smooth"
    });
    if (loading) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setLoading(false);
      abortControllerRef.current = null;
      setShowTyping(false);
      return;
    }
    const messageToSend = overrideInput !== undefined ? overrideInput : input;
    if (!messageToSend.trim()) return;
    setCentered(false); // Switch to chat layout after first message
    const userMessage: Message = { sender: "user", text: messageToSend };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");
    setLoading(true);
    setShowTyping(true); // Show typing indicator
    if (textareaRef.current) textareaRef.current.style.height = '55px';
    scrollToBottom();
    try {
      console.log('[Frontend] Sending message to backend:', messageToSend);
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const res = await fetch("http://localhost:5000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.text,
          history: messages, // send full message history
          session_id: sessionId,
        }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error("Failed to get response");
      let botText = "";
      let statusMessageActive = false;
      setMessages((msgs) => [...msgs, { sender: "bot", text: "" }]);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let firstChunk = true;
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          if (firstChunk) {
            setShowTyping(false); // Hide typing indicator on first chunk
            firstChunk = false;
          }
          // Simplified status message handling
          const chunk = decoder.decode(value);
          const isStatusChunk = chunk.startsWith('[Fetching') || chunk.startsWith('[Looking up') || chunk.startsWith('[Checking');

          if (isStatusChunk) {
            statusMessageActive = true;
            botText = chunk.trim(); // Overwrite with new status
            setMessages((msgs) => {
              const updated = [...msgs];
              updated[updated.length - 1] = { sender: "bot", text: botText };
              return updated;
            });
          } else {
            // This is a regular content chunk
            if (statusMessageActive) {
              // If we were previously showing a status, reset the text
              botText = ""; 
              statusMessageActive = false;
            }
            botText += chunk;
            setMessages((msgs) => {
              const updated = [...msgs];
              // Append new content. This will replace a status message if one was just active.
              updated[updated.length - 1] = { sender: "bot", text: botText };
              return updated;
            });
          }
          scrollToBottom();
          // console.log('[Frontend] Received chunk:', chunk);
          if (chunk.includes('Menu item found:')) {
            console.log('[Frontend] Backend: Queried MCP server and found the item.');
          }
          if (chunk.includes('is not on the menu')) {
            console.log('[Frontend] Backend: Queried MCP server and item was not found.');
          }
        }
      }
      setLoading(false);
      abortControllerRef.current = null;
      scrollToBottom();
      console.log('[Frontend] Streaming response finished.');
      setShowTyping(false); // Hide typing indicator if not already hidden
    } catch (err) {
      if ((err as any).name === 'AbortError') {
        // Don't remove the bot message when aborted - keep the partial response
        console.log('[Frontend] Streaming response aborted by user.');
        // Mark the last bot message as stopped
        setStoppedMessages(prev => new Set([...prev, messages.length]));
      } else {
        setMessages((msgs) => [
          ...msgs,
          { sender: "bot", text: "Sorry, there was an error connecting to the AI." },
        ]);
        console.error('[Frontend] Error connecting to backend:', err);
      }
      setLoading(false);
      abortControllerRef.current = null;
      scrollToBottom();
      setShowTyping(false); // Hide typing indicator on error
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      sendMessage();
    }
  };

  // Auto-resize textarea height up to 200px
  const handleInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = '55px'; // reset to min height
      textarea.style.minHeight = '55px'; // reset to min height
      let scrollHeight = Math.max(55, textarea.scrollHeight)
      textarea.style.height = Math.min(scrollHeight, 200) + 'px';
    }
    setInput(e.currentTarget.value);
  };

  // Suggestions for initial questions
  const suggestions = [
    { text: "What's on the menu", color: "#fdcb6e" },
    { text: "What's Open", color: "#7f6ec7" },
    { text: "Order a pepperoni pizza", color: "#3baecc" },
    { text: "What can you do for me", color: "#c66483" },
    { text: "How do I make online orders", color: "#43b47b" },
  ];

  // Helper to get greeting based on time of day
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good Morning";
    if (hour < 18) return "Good Afternoon";
    return "Good Evening";
  };

  // Helper for suggestion click
  const handleSuggestionClick = (text: string) => {
    setInput(text);
    sendMessage(text);
  };

  // Ensure the background color fills the whole page, even when scrolled
  useEffect(() => {
    document.body.style.background = '#191919';
    document.documentElement.style.background = '#191919';
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#191919",
      color: "#f3f3f3",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "flex-start",
      fontFamily: "Inter, sans-serif",
      width: '100vw',
      minWidth: 0,
    }}>
      <div style={{
        width: "100%",
        maxWidth: 750,
        margin: "40px auto 0 auto",
        // background: "#232326",
        borderRadius: 12,
        // boxShadow: "0 2px 16px 0 #0002",
        display: "flex",
        flexDirection: "column",
        minHeight: "90vh",
        background: 'transparent',
      }}>
        {/* Chat message list */}
        <div className='chat-message-list' style={{
          flex: 1,
          overflowY: 'auto',
          padding: 32,
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
          paddingBottom: 100,
          justifyContent: 'center',
        }}>
          {messages.length === 0 && (
            <div style={{color: '#fff', textAlign: 'center', fontSize: '1.5rem', position: 'relative'}}>
              {/* Purple radial gradient background */}
              <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '100%',
                height: '100%',
                zIndex: 0,
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(137,0,255,0.18) 0%, rgba(137,0,255,0.10) 20%, rgba(137,0,255,0.01) 80%)',
                filter: 'blur(40px)',
                pointerEvents: 'none',
              }} />
              {/* Mascot and greeting content (zIndex: 1) */}
              <div style={{position: 'relative', zIndex: 1}}>
                <MascotEyes />
                <div style={{ fontSize: '1.2rem', marginBottom: 8, color: '#bbb' }}>{getGreeting()}</div>
                How may I help you?
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  gap: 12,
                  marginTop: 24,
                  flexWrap: 'wrap',
                }}>
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSuggestionClick(s.text)}
                      style={{
                        background: '#171717',
                        color: s.color,
                        border: '1px solid #2b2b2b',
                        borderRadius: 20,
                        padding: '8px 18px',
                        fontSize: 15,
                        fontWeight: 500,
                        cursor: 'pointer',
                        boxShadow: '0 1px 4px #0002',
                        transition: 'background 0.2s',
                      }}
                    >
                      {s.text}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} style={{
              display: 'flex',
              justifyContent: msg.sender === "user" ? "flex-end" : "flex-start",
              position: 'relative',
              alignItems: 'flex-start',
            }}>
              {/* Stopped indicator for bot messages */}
              {msg.sender === 'bot' && stoppedMessages.has(idx) && (
                <div style={{
                  position: 'absolute',
                  top: -8,
                  right: 8,
                  background: '#666',
                  color: '#fff',
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '8px',
                  opacity: 0.7,
                  zIndex: 1,
                }}>
                  stopped
                </div>
              )}
              {/* Bot avatar for bot messages */}
              {msg.sender === 'bot' && (
                <div style={{
                  width: 32,
                  height: 32,
                  minWidth: 32,
                  minHeight: 32,
                  marginRight: 12,
                  marginTop: 16,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                }}>
                  <MascotEyesSmall />
                </div>
              )}
              <span style={{
                background: msg.sender === "user" ? "#303030" : "",
                color: '#f3f3f3',
                borderRadius: '1.5rem',
                padding: '12px 18px',
                maxWidth: msg.sender == "user" ? "60%" : "100%",
                fontSize: 17,
                lineHeight: 1.6,
                boxShadow: msg.sender === "user" ? "0 1px 4px #0002" : undefined,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                display: 'inline-block',
              }}>
                {/* Render bot messages as markdown, user messages as plain text */}
                {msg.sender === 'bot' ? (
                  <div>
                    {/* Special style for status messages */}
                    {msg.text.startsWith('[Fetching') || msg.text.startsWith('[Looking up') || msg.text.startsWith('[Checking') ? (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        fontWeight: 400,
                        fontSize: 16,
                        background: 'linear-gradient(90deg, #eee 0%, #333 50%, #eee 100%)',
                        backgroundSize: '200% 100%',
                        backgroundPosition: '0% 0%',
                        color: 'transparent',
                        WebkitBackgroundClip: 'text',
                        backgroundClip: 'text',
                        animation: 'shimmerGradient 2s linear infinite',
                        letterSpacing: 0.5,
                      }}>
                        {/* Spinner */}
                        <span style={{
                          display: 'inline-block',
                          width: 16,
                          height: 16,
                          marginRight: 2,
                          marginLeft: 6,
                          border: '2px solid #bbb',
                          borderTop: '2px solid #333',
                          borderRadius: '50%',
                          animation: 'spinLoader 0.8s linear infinite',
                        }} />
                        {msg.text}
                        <style>{`
                          @keyframes shimmerGradient {
                            0% { background-position: 200% 0%; }
                            100% { background-position: 0% 0%; }
                          }
                          @keyframes spinLoader {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                          }
                        `}</style>
                      </span>
                    ) : (
                      <ReactMarkdown 
                        rehypePlugins={[rehypeRaw]}
                        components={{
                          div: ({node, className, children, ...props}) => {
                            if (className === 'status-tag') {
                              return <div className={className} {...props}>{children}</div>;
                            }
                            return <div {...props}>{children}</div>;
                          }
                        }}
                      >
                        {msg.text}
                      </ReactMarkdown>
                    )}
                  </div>
                ) : (
                  msg.text
                )}
              </span>
            </div>
          ))}
          {/* Typing indicator */}
          {showTyping && (
            <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', height: 16, marginLeft: 8, position: 'relative' }}>
              <span style={{
                display: 'inline-block',
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: '#ffffff',
                animation: 'pulse 1.5s infinite',
                position: 'absolute',
                top: '-50px',
                left: '45px',
              }} />
              <style>{`
                @keyframes pulse {
                  0% { transform: scale(0.8); opacity: 1; }
                  50% { transform: scale(1); opacity: 1; }
                  100% { transform: scale(0.8); opacity: 1; }
                }
              `}</style>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        {/* Input box and send button */}
        <div style={{
          padding: 32,
          display: 'flex',
          alignItems: 'center',
          position: 'fixed',
          bottom: 0,
          background: 'linear-gradient(0deg,rgba(25, 25, 25, 1) 30%, rgba(25, 25, 25, 0) 100%)',
          maxWidth: 750,
          width: '100%'
        }}>
          <div style={{
            position: 'relative',
            flex: 1,
            display: 'flex',
            alignItems: 'flex-end',
          }}>
          <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onInput={handleInput}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask anything..."
              // disabled={loading}
              rows={1}
              style={{
                flex: 1,
                padding: '14px 48px 14px 16px',
                fontSize: 17,
                borderRadius: 12,
                border: '1px solid #313131',
                background: 'rgba(32, 32, 32, 0.9)',
                color: '#f3f3f3',
                outline: 'none',
                resize: 'none',
                minHeight: 32,
                maxHeight: 200,
                lineHeight: 1.5,
                boxSizing: 'border-box',
                overflowY: 'auto',
                fontFamily: 'Inter, sans-serif',
                backdropFilter: 'blur(40px)',
                boxShadow: 'rgba(0, 0, 0, 0.48) 0px 24px 48px -8px, rgba(0, 0, 0, 0.24) 0px 4px 12px -1px, rgba(255, 255, 255, 0.094) 0px 0px 0px 1px',
              }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() && !loading}
              style={{
                position: 'absolute',
                right: 54,
                bottom: 12,
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: 'transparent',
                color: '#fff',
                cursor: 'pointer',
                border: 'none',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                boxShadow: '0 2px 8px #0002',
                transition: 'opacity 0.2s',
                zIndex: 2,
              }}
              aria-label={loading ? "Stop generating" : "Speak"}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-label="" className="icon" fontSize="inherit"><path d="M15.7806 10.1963C16.1326 10.3011 16.3336 10.6714 16.2288 11.0234L16.1487 11.2725C15.3429 13.6262 13.2236 15.3697 10.6644 15.6299L10.6653 16.835H12.0833L12.2171 16.8486C12.5202 16.9106 12.7484 17.1786 12.7484 17.5C12.7484 17.8214 12.5202 18.0894 12.2171 18.1514L12.0833 18.165H7.91632C7.5492 18.1649 7.25128 17.8672 7.25128 17.5C7.25128 17.1328 7.5492 16.8351 7.91632 16.835H9.33527L9.33429 15.6299C6.775 15.3697 4.6558 13.6262 3.84992 11.2725L3.76984 11.0234L3.74445 10.8906C3.71751 10.5825 3.91011 10.2879 4.21808 10.1963C4.52615 10.1047 4.84769 10.2466 4.99347 10.5195L5.04523 10.6436L5.10871 10.8418C5.8047 12.8745 7.73211 14.335 9.99933 14.335C12.3396 14.3349 14.3179 12.7789 14.9534 10.6436L15.0052 10.5195C15.151 10.2466 15.4725 10.1046 15.7806 10.1963ZM12.2513 5.41699C12.2513 4.17354 11.2437 3.16521 10.0003 3.16504C8.75675 3.16504 7.74835 4.17343 7.74835 5.41699V9.16699C7.74853 10.4104 8.75685 11.418 10.0003 11.418C11.2436 11.4178 12.2511 10.4103 12.2513 9.16699V5.41699ZM13.5814 9.16699C13.5812 11.1448 11.9781 12.7479 10.0003 12.748C8.02232 12.748 6.41845 11.1449 6.41828 9.16699V5.41699C6.41828 3.43889 8.02221 1.83496 10.0003 1.83496C11.9783 1.83514 13.5814 3.439 13.5814 5.41699V9.16699Z"></path></svg>
            </button>
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() && !loading}
              style={{
                position: 'absolute',
                right: 12,
                bottom: 12,
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: '#fff',
                color: '#000',
                border: 'none',
                fontWeight: 600,
                cursor: (!input.trim() && !loading) ? 'not-allowed' : 'pointer',
                // opacity: (!input.trim() && !loading) ? 0.6 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                boxShadow: '0 2px 8px #0002',
                transition: 'opacity 0.2s',
                zIndex: 2,
              }}
              aria-label={loading && !input.trim() ? "Stop generating" : "Send"}
            >
              {loading && !input.trim() ? (
                // Square SVG for stop - only show when loading AND no input text
                <svg width="20" height="20" viewBox="0 0 20 20" fill="black" xmlns="http://www.w3.org/2000/svg" style={{display: 'block'}}><path d="M4.5 5.75C4.5 5.05964 5.05964 4.5 5.75 4.5H14.25C14.9404 4.5 15.5 5.05964 15.5 5.75V14.25C15.5 14.9404 14.9404 15.5 14.25 15.5H5.75C5.05964 15.5 4.5 14.9404 4.5 14.25V5.75Z"></path></svg>
              ) : (
                // Arrow SVG for send - show when not loading OR when there's input text
                <svg width="20" height="20" viewBox="0 0 20 20" fill="black" xmlns="http://www.w3.org/2000/svg" style={{display: 'block'}}><path d="M8.99992 16V6.41407L5.70696 9.70704C5.31643 10.0976 4.68342 10.0976 4.29289 9.70704C3.90237 9.31652 3.90237 8.6835 4.29289 8.29298L9.29289 3.29298L9.36907 3.22462C9.76184 2.90427 10.3408 2.92686 10.707 3.29298L15.707 8.29298L15.7753 8.36915C16.0957 8.76192 16.0731 9.34092 15.707 9.70704C15.3408 10.0732 14.7618 10.0958 14.3691 9.7754L14.2929 9.70704L10.9999 6.41407V16C10.9999 16.5523 10.5522 17 9.99992 17C9.44764 17 8.99992 16.5523 8.99992 16Z"></path></svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

