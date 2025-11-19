import oboe from 'oboe';

/**
 * Handles streaming JSON parsing with buffer management for incomplete chunks
 */
export class StreamingJsonParser {
  private buffer: string = '';
  private onChunkCallback: (data: any) => void;

  constructor(onChunk: (data: any) => void) {
    this.onChunkCallback = onChunk;
  }

  /**
   * Process a new chunk of data from the stream
   */
  processChunk(chunk: string): void {
    this.buffer += chunk;
    this.parseAvailableChunks();
  }

  /**
   * Process any remaining data in the buffer (call when stream is complete)
   */
  finalize(): void {
    if (this.buffer.trim()) {
      this.parseAvailableChunks();
      // If there's still unparsed data, try to extract partial JSON
      if (this.buffer.trim()) {
        this.handleRemainingBuffer();
      }
    }
  }

  /**
   * Handle any remaining incomplete data in the buffer
   */
  private handleRemainingBuffer(): void {
    const trimmedBuffer = this.buffer.trim();
    
    // Check if the remaining data looks like it could be part of a ["custom", {...}] structure
    if (trimmedBuffer.includes('["custom"') || trimmedBuffer.includes('"custom"')) {
      // Try to extract any complete JSON objects from the remaining data
      let searchIndex = 0;
      let foundAnyComplete = false;
      
      while (true) {
        const customIndex = trimmedBuffer.indexOf('["custom",', searchIndex);
        if (customIndex === -1) break;
        
        const openBraceIndex = trimmedBuffer.indexOf('{', customIndex);
        if (openBraceIndex === -1) break;
        
        const jsonString = this.extractJsonObject(trimmedBuffer, openBraceIndex);
        if (jsonString) {
          try {
            this.parseJsonWithOboe(jsonString);
            foundAnyComplete = true;
            const closingBracketIndex = trimmedBuffer.indexOf(']', openBraceIndex + jsonString.length);
            searchIndex = closingBracketIndex !== -1 ? closingBracketIndex + 1 : openBraceIndex + jsonString.length;
          } catch (e) {
            console.warn("Failed to parse remaining JSON chunk:", jsonString, e);
            searchIndex = openBraceIndex + 1;
          }
        } else {
          break;
        }
      }
      
      // Only warn if we couldn't parse any complete objects
      if (!foundAnyComplete) {
        console.warn('Unparsed data remaining in buffer:', this.buffer.slice(0, 200) + '...');
      }
    } else if (trimmedBuffer.length > 10) {
      // Only warn about non-trivial remaining data
      console.warn('Unparsed data remaining in buffer:', this.buffer.slice(0, 200) + '...');
    }
  }

  /**
   * Parse complete JSON objects from the buffer using oboe for robust parsing
   */
  private parseAvailableChunks(): void {
    let searchIndex = 0;
    
    while (true) {
      // Find the next ["custom", pattern
      const customIndex = this.buffer.indexOf('["custom",', searchIndex);
      if (customIndex === -1) break;
      
      // Find the opening brace after "custom",
      const openBraceIndex = this.buffer.indexOf('{', customIndex);
      if (openBraceIndex === -1) break;
      
      // Use bracket counting to find the matching closing brace
      const jsonString = this.extractJsonObject(this.buffer, openBraceIndex);
      if (!jsonString) {
        // Incomplete JSON object, wait for more data
        break;
      }
      
      // Find the closing bracket of the array
      const closingBracketIndex = this.buffer.indexOf(']', openBraceIndex + jsonString.length);
      if (closingBracketIndex === -1) {
        // Incomplete array, wait for more data
        break;
      }
      
      try {
        this.parseJsonWithOboe(jsonString);
        searchIndex = closingBracketIndex + 1;
      } catch (e) {
        console.warn("Failed to parse stream JSON chunk:", jsonString, e);
        searchIndex = openBraceIndex + 1; // Skip this attempt and continue
      }
    }

    // Keep unprocessed part of buffer for next chunk
    this.buffer = this.buffer.substring(searchIndex);
  }

  /**
   * Extract a complete JSON object using bracket counting
   */
  private extractJsonObject(buffer: string, startIndex: number): string | null {
    let braceCount = 0;
    let inString = false;
    let escaped = false;
    let i = startIndex;

    while (i < buffer.length) {
      const char = buffer[i];
      
      if (escaped) {
        escaped = false;
        i++;
        continue;
      }
      
      if (char === '\\' && inString) {
        escaped = true;
        i++;
        continue;
      }
      
      if (char === '"') {
        inString = !inString;
      } else if (!inString) {
        if (char === '{') {
          braceCount++;
        } else if (char === '}') {
          braceCount--;
          if (braceCount === 0) {
            // Found the matching closing brace
            return buffer.substring(startIndex, i + 1);
          }
        }
      }
      
      i++;
    }
    
    // Incomplete JSON object
    return null;
  }

  /**
   * Use oboe library for robust JSON parsing
   */
  private parseJsonWithOboe(jsonString: string): void {
    try {
      // First try standard JSON.parse for simple cases
      const parsed = JSON.parse(jsonString);
      this.onChunkCallback(parsed);
    } catch (e) {
      // If standard parsing fails, use oboe for more robust parsing
      let result: any = null;
      let hasError = false;

      oboe()
        .node('*', (data: any) => {
          result = data;
        })
        .fail((error: any) => {
          hasError = true;
          console.warn('Oboe parsing failed:', error, 'for JSON:', jsonString);
        })
        .done(() => {
          if (!hasError && result !== null) {
            this.onChunkCallback(result);
          }
        })
        .start(jsonString);
    }
  }

  /**
   * Clear the internal buffer (useful for resetting state)
   */
  reset(): void {
    this.buffer = '';
  }
}

/**
 * Enhanced stream reader that handles incomplete JSON chunks properly
 */
export class EnhancedStreamReader {
  private parser: StreamingJsonParser;
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private decoder: TextDecoder = new TextDecoder();

  constructor(onChunk: (data: any) => void) {
    this.parser = new StreamingJsonParser(onChunk);
  }

  /**
   * Read and process the entire stream
   */
  async readStream(response: Response): Promise<void> {
    if (!response.body) {
      throw new Error('ReadableStream not supported!');
    }

    this.reader = response.body.getReader();

    try {
      while (true) {
        const { value, done } = await this.reader.read();
        
        if (value) {
          // Decode the chunk and process it
          const chunk = this.decoder.decode(value, { stream: true });
          this.parser.processChunk(chunk);
        }

        if (done) {
          // Process any remaining data in the buffer
          this.parser.finalize();
          break;
        }
      }
    } finally {
      this.cleanup();
    }
  }

  /**
   * Clean up resources
   */
  private cleanup(): void {
    if (this.reader) {
      this.reader.releaseLock();
      this.reader = null;
    }
  }

  /**
   * Cancel the stream reading
   */
  async cancel(): Promise<void> {
    if (this.reader) {
      await this.reader.cancel();
      this.cleanup();
    }
  }
}