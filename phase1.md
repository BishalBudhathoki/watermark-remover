You are an expert Python developer specializing in API integrations. I need a **Twitter Video Downloader** built in Python.

### **Project Overview:**
- The script should **fetch video URLs** from Twitter posts and **download them**.
- It should use the **Twitter API** (v2) and handle authentication securely.
- The solution should be **efficient, scalable, and error-resistant**.

### **Tech Stack:**
- Programming Language: **Python**
- Libraries: **tweepy, requests**
- Authentication: **Twitter API (Bearer Token)**
- Video Handling: **Requests for file downloads**

### **Steps to Implement:**
1. **Obtain Twitter API credentials**  
   - The script should authenticate using the **Twitter API v2**.
   - Credentials should be stored securely using environment variables.
   
2. **Implement Authentication**  
   - Use **OAuth 2.0 Bearer Token** for accessing public tweets.
   - Handle authentication failures properly.

3. **Extract Video URLs**  
   - Parse the **tweet JSON response** to extract video URLs.
   - Support different video qualities (highest resolution preferred).

4. **Implement Download Functionality**  
   - Download videos using `requests` and save them locally.
   - Ensure downloads are resumable and handle large files efficiently.

5. **Handle Errors & Edge Cases**  
   - Handle **rate limits**, **private accounts**, and **non-video tweets** gracefully.
   - Provide meaningful error messages.

### **Additional Features (Optional but Preferred):**
- Allow downloading by **tweet URL or tweet ID**.
- Provide an option to **choose video resolution**.
- Multi-threaded downloads for speed optimization.
- CLI interface for easy usage.

### **Deliverables:**
- A **fully functional Python script** for downloading Twitter videos.
- Proper **error handling and logging**.
- Well-structured **code with comments** explaining key functions.
- Instructions on how to set up and run the script.

**Generate the complete working Python script for Twitter video downloading now!**
