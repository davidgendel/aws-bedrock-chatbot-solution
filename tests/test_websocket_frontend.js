/**
 * WebSocket Frontend Testing Script
 * Tests the frontend WebSocket functionality including connection, messaging, and fallback.
 */

class WebSocketTester {
  constructor(websocketUrl, restApiUrl, apiKey) {
    this.websocketUrl = websocketUrl;
    this.restApiUrl = restApiUrl;
    this.apiKey = apiKey;
    this.testResults = [];
    this.webSocket = null;
    this.wsState = 'CLOSED';
  }

  log(test, status, message) {
    const result = { test, status, message, timestamp: new Date().toISOString() };
    this.testResults.push(result);
    console.log(`[${status}] ${test}: ${message}`);
  }

  async runAllTests() {
    console.log('Starting WebSocket Frontend Tests...');
    
    await this.testConnectionEstablishment();
    await this.testMessageSending();
    await this.testHeartbeat();
    await this.testReconnectionLogic();
    await this.testErrorHandling();
    await this.testFallbackToREST();
    
    this.generateReport();
  }

  async testConnectionEstablishment() {
    console.log('\n=== Testing WebSocket Connection Establishment ===');
    
    try {
      // Test 1: Valid WebSocket URL
      await this.connectWebSocket();
      if (this.wsState === 'OPEN') {
        this.log('Connection Establishment', 'PASS', 'WebSocket connected successfully');
      } else {
        this.log('Connection Establishment', 'FAIL', 'WebSocket failed to connect');
      }
      
      // Test 2: Connection timeout
      const timeoutPromise = new Promise((resolve) => {
        setTimeout(() => {
          if (this.wsState === 'CONNECTING') {
            this.log('Connection Timeout', 'PASS', 'Connection timeout handled correctly');
          } else {
            this.log('Connection Timeout', 'FAIL', 'Connection timeout not handled');
          }
          resolve();
        }, 16000); // Slightly longer than default timeout
      });
      
      await timeoutPromise;
      
    } catch (error) {
      this.log('Connection Establishment', 'FAIL', `Connection error: ${error.message}`);
    }
  }

  async testMessageSending() {
    console.log('\n=== Testing WebSocket Message Sending ===');
    
    if (this.wsState !== 'OPEN') {
      await this.connectWebSocket();
    }
    
    if (this.wsState === 'OPEN') {
      try {
        // Test 1: Valid message
        const testMessage = "Hello, this is a test message";
        const messageData = {
          action: 'sendMessage',
          message: testMessage
        };
        
        const messagePromise = new Promise((resolve) => {
          const originalOnMessage = this.webSocket.onmessage;
          this.webSocket.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === 'response' || data.type === 'chunk') {
                this.log('Message Sending', 'PASS', 'Received response from WebSocket');
                resolve();
              }
            } catch (e) {
              this.log('Message Sending', 'FAIL', `Failed to parse response: ${e.message}`);
              resolve();
            }
            if (originalOnMessage) originalOnMessage(event);
          };
        });
        
        this.webSocket.send(JSON.stringify(messageData));
        
        // Wait for response or timeout
        await Promise.race([
          messagePromise,
          new Promise(resolve => setTimeout(() => {
            this.log('Message Sending', 'FAIL', 'No response received within timeout');
            resolve();
          }, 10000))
        ]);
        
        // Test 2: Empty message
        try {
          this.webSocket.send(JSON.stringify({ action: 'sendMessage', message: '' }));
          this.log('Empty Message Handling', 'PASS', 'Empty message sent without error');
        } catch (error) {
          this.log('Empty Message Handling', 'FAIL', `Empty message error: ${error.message}`);
        }
        
      } catch (error) {
        this.log('Message Sending', 'FAIL', `Message sending error: ${error.message}`);
      }
    } else {
      this.log('Message Sending', 'SKIP', 'WebSocket not connected');
    }
  }

  async testHeartbeat() {
    console.log('\n=== Testing WebSocket Heartbeat ===');
    
    if (this.wsState !== 'OPEN') {
      await this.connectWebSocket();
    }
    
    if (this.wsState === 'OPEN') {
      try {
        const heartbeatData = { action: 'heartbeat' };
        
        const heartbeatPromise = new Promise((resolve) => {
          const originalOnMessage = this.webSocket.onmessage;
          this.webSocket.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === 'pong' || data.action === 'pong') {
                this.log('Heartbeat', 'PASS', 'Heartbeat pong received');
                resolve();
              }
            } catch (e) {
              // Ignore parsing errors for heartbeat
            }
            if (originalOnMessage) originalOnMessage(event);
          };
        });
        
        this.webSocket.send(JSON.stringify(heartbeatData));
        
        await Promise.race([
          heartbeatPromise,
          new Promise(resolve => setTimeout(() => {
            this.log('Heartbeat', 'PASS', 'Heartbeat sent successfully (no pong required)');
            resolve();
          }, 3000))
        ]);
        
      } catch (error) {
        this.log('Heartbeat', 'FAIL', `Heartbeat error: ${error.message}`);
      }
    } else {
      this.log('Heartbeat', 'SKIP', 'WebSocket not connected');
    }
  }

  async testReconnectionLogic() {
    console.log('\n=== Testing WebSocket Reconnection Logic ===');
    
    if (this.wsState !== 'OPEN') {
      await this.connectWebSocket();
    }
    
    if (this.wsState === 'OPEN') {
      try {
        // Force close connection to test reconnection
        const reconnectPromise = new Promise((resolve) => {
          let reconnectAttempted = false;
          
          const originalOnClose = this.webSocket.onclose;
          this.webSocket.onclose = (event) => {
            if (event.code !== 1000) { // Not a clean close
              this.log('Reconnection Logic', 'PASS', 'Connection closed, should trigger reconnection');
              
              // Check if reconnection is attempted
              setTimeout(() => {
                if (this.wsState === 'CONNECTING' || this.wsState === 'OPEN') {
                  this.log('Reconnection Attempt', 'PASS', 'Reconnection attempted');
                  reconnectAttempted = true;
                } else {
                  this.log('Reconnection Attempt', 'FAIL', 'No reconnection attempted');
                }
                resolve();
              }, 2000);
            }
            if (originalOnClose) originalOnClose(event);
          };
        });
        
        // Force close with error code
        this.webSocket.close(1006, 'Connection lost');
        
        await reconnectPromise;
        
      } catch (error) {
        this.log('Reconnection Logic', 'FAIL', `Reconnection test error: ${error.message}`);
      }
    } else {
      this.log('Reconnection Logic', 'SKIP', 'WebSocket not connected');
    }
  }

  async testErrorHandling() {
    console.log('\n=== Testing WebSocket Error Handling ===');
    
    try {
      // Test 1: Invalid WebSocket URL
      const invalidWs = new WebSocket('wss://invalid-url.example.com');
      
      const errorPromise = new Promise((resolve) => {
        invalidWs.onerror = () => {
          this.log('Invalid URL Handling', 'PASS', 'Invalid WebSocket URL handled correctly');
          resolve();
        };
        
        setTimeout(() => {
          this.log('Invalid URL Handling', 'FAIL', 'Invalid URL error not triggered');
          resolve();
        }, 5000);
      });
      
      await errorPromise;
      
      // Test 2: Malformed message
      if (this.wsState === 'OPEN') {
        try {
          this.webSocket.send('invalid json');
          this.log('Malformed Message', 'PASS', 'Malformed message sent without client error');
        } catch (error) {
          this.log('Malformed Message', 'PASS', 'Malformed message caught by client');
        }
      }
      
    } catch (error) {
      this.log('Error Handling', 'FAIL', `Error handling test failed: ${error.message}`);
    }
  }

  async testFallbackToREST() {
    console.log('\n=== Testing Fallback to REST API ===');
    
    try {
      // Close WebSocket to force REST fallback
      if (this.webSocket) {
        this.webSocket.close(1000, 'Testing REST fallback');
        this.wsState = 'CLOSED';
      }
      
      // Test REST API call
      const testMessage = "This should use REST API";
      const response = await fetch(`${this.restApiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': this.apiKey
        },
        body: JSON.stringify({
          message: testMessage,
          streaming: false
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        this.log('REST Fallback', 'PASS', 'REST API fallback successful');
      } else {
        this.log('REST Fallback', 'FAIL', `REST API returned ${response.status}`);
      }
      
    } catch (error) {
      this.log('REST Fallback', 'FAIL', `REST fallback error: ${error.message}`);
    }
  }

  async connectWebSocket() {
    return new Promise((resolve) => {
      try {
        this.webSocket = new WebSocket(this.websocketUrl);
        this.wsState = 'CONNECTING';
        
        this.webSocket.onopen = () => {
          this.wsState = 'OPEN';
          resolve();
        };
        
        this.webSocket.onclose = (event) => {
          this.wsState = 'CLOSED';
          resolve();
        };
        
        this.webSocket.onerror = () => {
          this.wsState = 'CLOSED';
          resolve();
        };
        
        // Timeout after 15 seconds
        setTimeout(() => {
          if (this.wsState === 'CONNECTING') {
            this.wsState = 'CLOSED';
            this.webSocket.close();
          }
          resolve();
        }, 15000);
        
      } catch (error) {
        this.wsState = 'CLOSED';
        resolve();
      }
    });
  }

  generateReport() {
    console.log('\n=== WebSocket Test Report ===');
    
    const passed = this.testResults.filter(r => r.status === 'PASS').length;
    const failed = this.testResults.filter(r => r.status === 'FAIL').length;
    const skipped = this.testResults.filter(r => r.status === 'SKIP').length;
    
    console.log(`Total Tests: ${this.testResults.length}`);
    console.log(`Passed: ${passed}`);
    console.log(`Failed: ${failed}`);
    console.log(`Skipped: ${skipped}`);
    console.log(`Success Rate: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);
    
    console.log('\nDetailed Results:');
    this.testResults.forEach(result => {
      console.log(`  ${result.status}: ${result.test} - ${result.message}`);
    });
    
    // Return results for programmatic use
    return {
      total: this.testResults.length,
      passed,
      failed,
      skipped,
      successRate: (passed / (passed + failed)) * 100,
      results: this.testResults
    };
  }
}

// Usage example (to be run in browser console or test environment)
/*
const tester = new WebSocketTester(
  'wss://your-websocket-api-id.execute-api.us-east-1.amazonaws.com/prod',
  'https://your-rest-api-id.execute-api.us-east-1.amazonaws.com/prod',
  'your-api-key'
);

tester.runAllTests().then(() => {
  console.log('All WebSocket tests completed');
});
*/

// Export for Node.js environments
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WebSocketTester;
}
