# Stop Button Behavior

## ✅ **New Implementation**

### **What happens when you click the stop button:**

1. **Generation stops immediately** - The streaming response is aborted
2. **Partial response is preserved** - The text that was already generated remains visible
3. **Subtle "stopped" indicator** - A small gray badge appears on the message
4. **UI returns to normal** - Loading state is cleared, stop button becomes send button

### **Before vs After:**

**Before:**
- Click stop → Entire bot message disappears
- User loses all generated content
- Confusing experience

**After:**
- Click stop → Generation stops, partial text remains
- User keeps what was already generated
- Clear visual feedback with "stopped" indicator

### **Technical Details:**

- Uses `AbortController` to cancel the fetch request
- Tracks stopped messages in `stoppedMessages` state
- Preserves partial responses instead of removing them
- Shows subtle visual indicator for stopped messages

### **User Experience:**

✅ **Preserves work** - No lost content  
✅ **Clear feedback** - User knows generation was stopped  
✅ **Seamless interaction** - Can immediately start new conversation  
✅ **Professional feel** - Similar to ChatGPT's behavior  

### **Visual Indicator:**

The "stopped" indicator appears as a small gray badge on the top-right of bot messages that were stopped mid-generation. It's subtle but clear enough to inform the user that the response was interrupted. 