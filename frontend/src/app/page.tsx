"use client"
import { useState, useRef, useEffect } from "react";
import styles from "./page.module.css";
import ReactMarkdown from 'react-markdown';

// Chat message type
interface Message {
  sender: "user" | "bot";
  text: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const sendMessage = async () => {
    if (loading) {
      // If loading, terminate the response
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      return;
    }
    if (!input.trim()) return;
    const userMessage: Message = { sender: "user", text: input };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");
    setLoading(true);
    // Reset textarea height after sending
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    scrollToBottom();
    try {
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const res = await fetch("http://localhost:5000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error("Failed to get response");
      let botText = "";
      setMessages((msgs) => [...msgs, { sender: "bot", text: "" }]);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          botText += chunk;
          setMessages((msgs) => {
            const updated = [...msgs];
            updated[updated.length - 1] = { sender: "bot", text: botText };
            return updated;
          });
          scrollToBottom();
        }
      }
      setLoading(false);
      abortControllerRef.current = null;
      scrollToBottom();
    } catch (err) {
      if ((err as any).name === 'AbortError') {
        setMessages((msgs) => {
          // Remove the last (incomplete) bot message
          if (msgs[msgs.length - 1]?.sender === 'bot') {
            return msgs.slice(0, -1);
          }
          return msgs;
        });
      } else {
        setMessages((msgs) => [
          ...msgs,
          { sender: "bot", text: "Sorry, there was an error connecting to the AI." },
        ]);
      }
      setLoading(false);
      abortControllerRef.current = null;
      scrollToBottom();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading) {
      sendMessage();
    }
  };

  // Auto-resize textarea height up to 200px
  const handleInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = '32px'; // reset to min height
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
    setInput(e.currentTarget.value);
  };

  // Suggestions for initial questions
  const suggestions = [
    { text: "What's on the menu", color: "#fdcb6e" },
    { text: "What's Open", color: "#7f6ec7" },
    { text: "Order a pizza", color: "#3baecc" },
    { text: "What's my meal plan balance", color: "#c66483" },
    { text: "How do I order online", color: "#43b47b" },
  ];

  // Helper to get greeting based on time of day
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good Morning";
    if (hour < 18) return "Good Afternoon";
    return "Good Evening";
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
        <div style={{
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
            <div style={{color: '#fff', textAlign: 'center', fontSize: '1.5rem'}}>
              {/* <img src="logo.png" style={{width: 100, height: 100, display: 'block', marginRight: 'auto', marginLeft: 'auto', marginBottom: 30, userSelect: 'none', pointerEvents: 'none'}}></img> */}
              <svg width="80" height="80" viewBox="0 0 328 286" style={{marginRight: 'auto', marginLeft: 'auto', marginBottom: 30, display: 'block'}} fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M261.768 238.869L212.482 225.691L248.59 189.583L261.768 238.869Z" fill="url(#paint0_linear_4_73)"/>
                <path d="M265 138C265 193.228 220.228 238 165 238C109.772 238 65 193.228 65 138C65 82.7715 109.772 38 165 38C220.228 38 265 82.7715 265 138Z" fill="url(#paint1_linear_4_73)"/>
                <path d="M0 118C0 109.163 7.16344 102 16 102H30C38.8366 102 46 109.163 46 118V163C46 171.837 38.8366 179 30 179H16C7.16344 179 0 171.837 0 163V118Z" fill="url(#paint2_linear_4_73)"/>
                <path d="M282 119C282 110.163 289.163 103 298 103H312C320.837 103 328 110.163 328 119V164C328 172.837 320.837 180 312 180H298C289.163 180 282 172.837 282 164V119Z" fill="url(#paint3_linear_4_73)"/>
                <path d="M164.5 0C240.439 0 302 61.5608 302 137.5C302 152.332 299.652 166.616 295.307 180H274.076C279.192 166.82 282 152.488 282 137.5C282 72.6065 229.393 20 164.5 20C99.6065 20 47 72.6065 47 137.5C47 202.393 99.6065 255 164.5 255C167.019 255 169.52 254.92 172 254.764V274.797C169.517 274.93 167.016 275 164.5 275C88.5608 275 27 213.439 27 137.5C27 61.5608 88.5608 0 164.5 0Z" fill="url(#paint4_linear_4_73)"/>
                <path d="M182 268C182 277.941 173.941 286 164 286C154.059 286 146 277.941 146 268C146 258.059 154.059 250 164 250C173.941 250 182 258.059 182 268Z" fill="url(#paint5_linear_4_73)"/>
                <defs>
                <linearGradient id="paint0_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                <linearGradient id="paint1_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                <linearGradient id="paint2_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                <linearGradient id="paint3_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                <linearGradient id="paint4_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                <linearGradient id="paint5_linear_4_73" x1="164" y1="0" x2="164" y2="286" gradientUnits="userSpaceOnUse">
                <stop stopColor="white"/>
                <stop offset="1" stopColor="#999999"/>
                </linearGradient>
                </defs>
            </svg>
              
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
                    onClick={() => setInput(s.text)}
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
          )}
          {messages.map((msg, idx) => (
            <div key={idx} style={{
              display: 'flex',
              justifyContent: msg.sender === "user" ? "flex-end" : "flex-start",
            }}>
              <span style={{
                background: msg.sender === "user" ? "#303030" : "",
                color: '#f3f3f3',
                borderRadius: '1.5rem',
                padding: '12px 18px',
                maxWidth: '100%',
                fontSize: 17,
                lineHeight: 1.6,
                boxShadow: msg.sender === "user" ? "0 1px 4px #0002" : undefined,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {/* Render bot messages as markdown, user messages as plain text */}
                {msg.sender === 'bot' ? (
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                ) : (
                  msg.text
                )}
              </span>
            </div>
          ))}
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
                if (e.key === "Enter" && !e.shiftKey && !loading) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask anything..."
              disabled={loading}
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
              onClick={sendMessage}
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
                opacity: (!input.trim() && !loading) ? 0.6 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                boxShadow: '0 2px 8px #0002',
                transition: 'opacity 0.2s',
                zIndex: 2,
              }}
              aria-label={loading ? "Stop generating" : "Send"}
            >
              {loading ? (
                // Square SVG for stop
                <svg width="20" height="20" viewBox="0 0 20 20" fill="black" xmlns="http://www.w3.org/2000/svg" style={{display: 'block'}}><path d="M4.5 5.75C4.5 5.05964 5.05964 4.5 5.75 4.5H14.25C14.9404 4.5 15.5 5.05964 15.5 5.75V14.25C15.5 14.9404 14.9404 15.5 14.25 15.5H5.75C5.05964 15.5 4.5 14.9404 4.5 14.25V5.75Z"></path></svg>
              ) : (
                // Arrow SVG for send
                <svg width="20" height="20" viewBox="0 0 20 20" fill="black" xmlns="http://www.w3.org/2000/svg" style={{display: 'block'}}><path d="M8.99992 16V6.41407L5.70696 9.70704C5.31643 10.0976 4.68342 10.0976 4.29289 9.70704C3.90237 9.31652 3.90237 8.6835 4.29289 8.29298L9.29289 3.29298L9.36907 3.22462C9.76184 2.90427 10.3408 2.92686 10.707 3.29298L15.707 8.29298L15.7753 8.36915C16.0957 8.76192 16.0731 9.34092 15.707 9.70704C15.3408 10.0732 14.7618 10.0958 14.3691 9.7754L14.2929 9.70704L10.9999 6.41407V16C10.9999 16.5523 10.5522 17 9.99992 17C9.44764 17 8.99992 16.5523 8.99992 16Z"></path></svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
