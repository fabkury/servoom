
/*
 * Decoder naming conventions
 *
 * The native library stores decoder state in opaque memory blocks that are
 * addressed via integer offsets.  To improve readability we follow the
 * conventions below when renaming variables:
 *  - decoderHandle / decoderStateAddress: base pointer to the decoder state.
 *  - inputData / inputBuffer: raw animation data that is being parsed.
 *  - frameOffset / chunkOffset: cursor inside the encoded stream.
 *  - workingInputBuffer: mutable copy of the input when ownership is required.
 *  - paletteTable / colorLookup: temporary colour tables extracted from frames.
 *  - bitCursor / bitCount: track bit level decoding progress.
 *  - tileX / tileY / blockIndex: identify tiles within large pixel blocks.
 * These names are reused across helpers so that equivalent concepts share the
 * same identifier.
 */

 ulong divoom_image_decode_add_data(ulong decoderHandle, void *inputData,int inputLength,int copySourceBuffer)

 {
   void *workingInputBuffer;
   uint frameOffset;
   ulong validFrameCount;
   
   if (decoderHandle != 0) {
     if (*(void **)(decoderHandle + 0x18) != (void *)0x0) {
       free(*(void **)(decoderHandle + 0x18));
       *(undefined8 *)(decoderHandle + 0x18) = 0;
     }
     *(int *)(decoderHandle + 4) = inputLength;
     *(undefined4 *)(decoderHandle + 0xc) = 0;
     workingInputBuffer = inputData;
     if (copySourceBuffer != 0) {
       workingInputBuffer = malloc((long)(inputLength << 1));
       *(void **)(decoderHandle + 0x18) = workingInputBuffer;
       memcpy(workingInputBuffer,inputData,(long)inputLength);
     }
     *(void **)(decoderHandle + 0x10) = workingInputBuffer;
     if (inputLength < 1) {
       validFrameCount = 0;
     }
     else {
       frameOffset = 0;
       validFrameCount = 0;
       do {
         if (*(char *)((long)inputData + (ulong)frameOffset) != -0x56) {
           return validFrameCount;
         }
         validFrameCount = (ulong)((int)validFrameCount + 1);
         frameOffset = *(ushort *)((long)inputData + (ulong)frameOffset + 1) + frameOffset;
       } while ((int)frameOffset < inputLength);
     }
   }
   else {
     validFrameCount = decoderHandle;
   }
   return validFrameCount;
 }
 
 
 bool divoom_image_decode_check_convert_net(long frameHeaderAddress)
 
 {
   return (*(byte *)(frameHeaderAddress + 5) & 0xfe) != 0x14;
 }
 
 
 bool divoom_image_decode_check_decode(long decoderStateAddress)
 
 {
   uint totalDataLength;
   uint consumedBytes;
   ushort frameLength;
   bool isFrameAvailable;
   
   if (decoderStateAddress == 0) {
     printf("err: %d!\n",0x16ff);
     isFrameAvailable = false;
   }
   else {
     totalDataLength = *(uint *)(decoderStateAddress + 8);
     consumedBytes = *(uint *)(decoderStateAddress + 0xc);
     if (consumedBytes + 7 < totalDataLength) {
       frameLength = *(ushort *)(*(long *)(decoderStateAddress + 0x10) + (ulong)consumedBytes + 1);
       printf("<%d,%d,%d, %d>\n",(ulong)totalDataLength,(ulong)consumedBytes,(ulong)frameLength,(ulong)*(uint *)(decoderStateAddress + 4)
             );
       isFrameAvailable = *(int *)(decoderStateAddress + 0xc) + (uint)frameLength <= *(uint *)(decoderStateAddress + 8);
     }
     else {
       isFrameAvailable = totalDataLength == *(uint *)(decoderStateAddress + 4);
     }
   }
   return isFrameAvailable;
 }
 
 
 bool divoom_image_decode_check_image(char *frameHeader)
 
 {
   if (*frameHeader == -0x56) {
     return (frameHeader[5] & 0x7fU) < 9;
   }
   return false;
 }
 
 
 uint divoom_image_decode_check_pic_iframe(long frameHeaderAddress)
 
 {
   uint result;
   
   result = 0x1010001 >> (ulong)((*(byte *)(frameHeaderAddress + 5) & 3) << 3);
   if (3 < *(byte *)(frameHeaderAddress + 5)) {
     result = 0;
   }
   return result;
 }
 
 
 void divoom_image_decode_creat_handle(void)
 
 {
   undefined8 *decoderState;
   
   decoderState = (undefined8 *)malloc(0x50);
   if (decoderState != (undefined8 *)0x0) {
     decoderState[4] = 0;
     decoderState[1] = 0;
     *decoderState = 0;
     decoderState[3] = 0;
     decoderState[2] = 0;
   }
   return;
 }
 
 
 uint divoom_image_decode_decode_all
                (long encodedStreamBase,int encodedStreamLength,long outputPixelBuffer,undefined8 userContext,
                uint requestedFormat,void *diagnosticBuffer)
 
 {
   uint pixelIndex;
   long destinationBlockAddress;
   undefined1 *destinationPixel;
   undefined1 *sourcePixel;
   uint formatByte;
   uint columnIndex;
   undefined2 rgb565Pair;
   ushort wordBlockLength;
   uint decodeStatus;
   undefined8 *frameState;
   ulong frameOffset;
   short paletteWriteIndex;
   uint rowIndex;
   uint frameCount;
   int frameIndex;
   ulong chunkIndex;
   int formatStride;
   
   if (encodedStreamBase == 0) {
     return 0;
   }
   if (outputPixelBuffer == 0) {
     return 0;
   }
   formatByte = requestedFormat & 0xff;
   if (formatByte < 0x40) {
     if (formatByte == 0x10) {
       frameIndex = 0x300;
       formatStride = 0x300;
     }
     else {
       if (formatByte != 0x20) {
         return 0;
       }
 LAB_0025f428:
       frameIndex = 0xc000;
       formatStride = 0xc000;
     }
   }
   else {
     if (formatByte == 0x80) goto LAB_0025f428;
     if (formatByte != 0x40) {
       return 0;
     }
     frameIndex = 0x3000;
     formatStride = 0x3000;
   }
   if (diagnosticBuffer != (void *)0x0) {
     memset(diagnosticBuffer,0,0x1216);
     formatStride = frameIndex;
   }
   frameState = (undefined8 *)malloc(0x50);
   if (frameState == (undefined8 *)0x0) {
     return 0;
   }
   frameState[4] = 0;
   frameState[1] = 0;
   *frameState = 0;
   frameState[3] = 0;
   frameState[2] = 0;
   *(int *)((long)frameState + 4) = encodedStreamLength;
   frameState[2] = encodedStreamBase;
   if (0 < encodedStreamLength) {
     decodeStatus = 0;
     frameCount = 0;
     do {
       if (*(char *)(encodedStreamBase + (ulong)decodeStatus) != -0x56) {
         if (frameCount == 0) goto LAB_0025f6f4;
         break;
       }
       frameCount = frameCount + 1;
       decodeStatus = *(ushort *)(encodedStreamBase + (ulong)decodeStatus + 1) + decodeStatus;
     } while ((int)decodeStatus < encodedStreamLength);
     frameOffset = 0;
     chunkIndex = 0;
     if (encodedStreamLength == 0) goto LAB_0025f508;
     do {
       if (*(char *)(frameState[2] + (ulong)((int)frameOffset + 5)) != '\x05') goto LAB_0025f518;
       wordBlockLength = divoom_image_decode_get_word_info(frameState[2] + frameOffset,diagnosticBuffer);
       *(uint *)((long)frameState + 0xc) = *(int *)((long)frameState + 0xc) + (uint)wordBlockLength;
       while( true ) {
         chunkIndex = chunkIndex + 1;
         if (chunkIndex == frameCount) goto LAB_0025f6f4;
         frameOffset = (ulong)*(uint *)((long)frameState + 0xc);
         if (*(uint *)((long)frameState + 0xc) < *(uint *)((long)frameState + 4)) break;
 LAB_0025f508:
         printf("err: %d!\n",0x18f3);
 LAB_0025f518:
         frameIndex = (int)chunkIndex;
         decodeStatus = divoom_image_decode_decode_pic
                           (frameState,outputPixelBuffer + (ulong)(uint)(formatStride * frameIndex),
                            userContext);
         if ((requestedFormat & 0xff) < (decodeStatus & 0xff)) {
           printf("pic size err: %d, %d, %d!\n",0x1646,(ulong)(decodeStatus & 0xff),(ulong)formatByte);
           goto LAB_0025f6f4;
         }
         if ((decodeStatus & 0xff) == 0) {
           printf("pic decode err: %d, %d!\n",0x164b,0);
           goto LAB_0025f6f4;
         }
         if ((decodeStatus & 0xff) < (requestedFormat & 0xff)) {
           if ((requestedFormat & 0xff) == 0x40) {
             destinationBlockAddress = outputPixelBuffer + (ulong)(uint)(frameIndex * 0x3000);
             if ((decodeStatus & 0xff) == 0x10) {
               paletteWriteIndex = 0xfff;
               decodeStatus = 0x3f;
               do {
                 rowIndex = 0x3f;
                 do {
                   columnIndex = rowIndex & 0xffff;
                   rowIndex = rowIndex - 1;
                   pixelIndex = (decodeStatus & 0x3ffffffc) * 4 + (columnIndex >> 2);
                   wordBlockLength = paletteWriteIndex * 3;
                   sourcePixel = (undefined1 *)
                                 (destinationBlockAddress + ((ulong)pixelIndex & 0xffff) +
                                 (ulong)(ushort)pixelIndex * 2);
                   paletteWriteIndex = paletteWriteIndex + -1;
                   destinationPixel = (undefined1 *)(destinationBlockAddress + (ulong)wordBlockLength);
                   rgb565Pair = *(undefined2 *)(sourcePixel + 1);
                   *destinationPixel = *sourcePixel;
                   *(undefined2 *)(destinationPixel + 1) = rgb565Pair;
                 } while (columnIndex != 0);
                 rowIndex = decodeStatus & 0xffff;
                 decodeStatus = decodeStatus - 1;
               } while (rowIndex != 0);
             }
             else {
               paletteWriteIndex = 0xfff;
               decodeStatus = 0x3f;
               do {
                 rowIndex = 0x3f;
                 do {
                   columnIndex = rowIndex & 0xffff;
                   rowIndex = rowIndex - 1;
                   pixelIndex = (decodeStatus & 0xffffffe) * 0x10 + (columnIndex >> 1);
                   wordBlockLength = paletteWriteIndex * 3;
                   sourcePixel = (undefined1 *)
                                 (destinationBlockAddress + ((ulong)pixelIndex & 0xffff) +
                                 (ulong)(ushort)pixelIndex * 2);
                   paletteWriteIndex = paletteWriteIndex + -1;
                   destinationPixel = (undefined1 *)(destinationBlockAddress + (ulong)wordBlockLength);
                   rgb565Pair = *(undefined2 *)(sourcePixel + 1);
                   *destinationPixel = *sourcePixel;
                   *(undefined2 *)(destinationPixel + 1) = rgb565Pair;
                 } while (columnIndex != 0);
                 rowIndex = decodeStatus & 0xffff;
                 decodeStatus = decodeStatus - 1;
               } while (rowIndex != 0);
             }
           }
           else if ((requestedFormat & 0xff) == 0x20) {
             frameOffset = 0x3ff;
             destinationBlockAddress = outputPixelBuffer + (ulong)(uint)(frameIndex * 0xc00);
             decodeStatus = 0x1f;
             do {
               rowIndex = 0x1f;
               do {
                 columnIndex = rowIndex & 0xffff;
                 rowIndex = rowIndex - 1;
                 pixelIndex = (decodeStatus & 0x1ffffffe) * 8 + (columnIndex >> 1);
                 destinationPixel = (undefined1 *)(destinationBlockAddress +
                                                  ((ulong)pixelIndex & 0xffff) +
                                                  (ulong)(ushort)pixelIndex * 2);
                 sourcePixel = (undefined1 *)(destinationBlockAddress + (frameOffset & 0xffff) +
                                              (frameOffset & 0xffff) * 2);
                 frameOffset = (ulong)((int)frameOffset - 1);
                 rgb565Pair = *(undefined2 *)(destinationPixel + 1);
                 *sourcePixel = *destinationPixel;
                 *(undefined2 *)(sourcePixel + 1) = rgb565Pair;
               } while (columnIndex != 0);
               rowIndex = decodeStatus & 0xffff;
               decodeStatus = decodeStatus - 1;
             } while (rowIndex != 0);
           }
         }
       }
     } while( true );
   }
   frameCount = 0;
 LAB_0025f6f8:
   if ((void *)frameState[3] != (void *)0x0) {
     free((void *)frameState[3]);
   }
   if ((void *)frameState[4] != (void *)0x0) {
     free((void *)frameState[4]);
   }
   free(frameState);
   return frameCount;
 LAB_0025f6f4:
   if (frameState == (undefined8 *)0x0) {
     return frameCount;
   }
   goto LAB_0025f6f8;
 }
 
 
 uint divoom_image_decode_decode_fix_16
                (long decoderStateAddress,char *blockDescriptor,long frameBuffer,int blockColumn,
                int blockRow,long paletteSource,int paletteBitDepth)
 
 {
   byte currentByte;
   byte paletteBitCount;
   bool continueProcessing;
   bool isFirstBlock;
   int tileRowIndex;
   int tileRowLimit;
   uint paletteEntryCount;
   long upperRowAddress;
   long lowerRowAddress;
   long rowBaseAddress;
   uint bitOffset;
   uint paletteLookupIndex;
   short paletteCacheIndex;
   byte *bitstreamCursor;
   int blockPixelOffset;
   ulong paletteBitMask;
   ulong paletteEntryCounter;
   undefined1 *paletteCacheCursor;
   uint bitAccumulator;
   uint remainingBits;
   undefined1 *paletteCacheWrite;
   undefined1 *paletteCacheTail;
   
   bitstreamCursor = (byte *)(blockDescriptor + 1);
   paletteCacheWrite = (undefined1 *)(decoderStateAddress + 0x110);
   paletteEntryCount = 0x100;
   if (*bitstreamCursor != 0) {
     paletteEntryCount = (uint)*bitstreamCursor;
   }
   if (*blockDescriptor == '\x02') {
     if (paletteEntryCount == 0) {
       paletteEntryCounter = 0;
     }
     else {
       paletteBitMask = 0;
       paletteEntryCounter = 0;
       do {
         paletteCacheTail = paletteCacheWrite;
         if (((byte)blockDescriptor[(paletteBitMask >> 3 & 0x1fffffff) + 2] >>
              (ulong)((uint)paletteBitMask & 7) & 1) != 0) {
           paletteEntryCounter = (ulong)((int)paletteEntryCounter + 1);
           paletteCacheTail = paletteCacheWrite + 1;
           *paletteCacheWrite = *(undefined1 *)(paletteSource + paletteBitMask);
         }
         paletteBitMask = paletteBitMask + 1;
         paletteCacheWrite = paletteCacheTail;
       } while (paletteEntryCount != paletteBitMask);
     }
     remainingBits = 0;
     paletteEntryCount = paletteEntryCount + 7 >> 3;
     paletteBitCount = (&gdivoom_image_bits_table)[paletteEntryCounter & 0xffff];
     blockPixelOffset = blockColumn * 0x30 + blockRow * 0x1800;
     bitstreamCursor = (byte *)(blockDescriptor + (ulong)paletteEntryCount + 2);
     tileRowLimit = blockPixelOffset + 0x18;
     bitAccumulator = 8 - paletteBitCount;
     isFirstBlock = true;
     do {
       continueProcessing = isFirstBlock;
       tileRowIndex = 0;
       lowerRowAddress = frameBuffer + tileRowLimit;
       upperRowAddress = frameBuffer + blockPixelOffset;
       do {
         rowBaseAddress = 0;
         do {
           bitOffset = remainingBits + paletteBitCount;
           currentByte = *bitstreamCursor;
           if ((int)bitOffset < 9) {
             if (bitOffset == 8) {
               bitstreamCursor = bitstreamCursor + 1;
             }
             paletteLookupIndex =
                  ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(bitAccumulator & 0x1f);
             remainingBits = 0;
             if (bitOffset != 8) {
               remainingBits = bitOffset;
             }
           }
           else {
             bitstreamCursor = bitstreamCursor + 1;
             paletteLookupIndex =
                  ((uint)*bitstreamCursor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(bitAccumulator & 0x1f) | (uint)(currentByte >> (ulong)(remainingBits & 0x1f));
             remainingBits = bitOffset - 8;
           }
           paletteCacheWrite = (undefined1 *)
                               (*(long *)(decoderStateAddress + 8) +
                               (ulong)*(byte *)(decoderStateAddress + (ulong)paletteLookupIndex + 0x110)
                               * 3)
           ;
           paletteCacheCursor = (undefined1 *)(upperRowAddress + rowBaseAddress);
           rowBaseAddress = rowBaseAddress + 3;
           *paletteCacheCursor = *paletteCacheWrite;
           paletteCacheCursor[1] = paletteCacheWrite[1];
           paletteCacheCursor[2] = paletteCacheWrite[2];
         } while ((int)rowBaseAddress != 0x18);
         tileRowIndex = tileRowIndex + 1;
         upperRowAddress = upperRowAddress + 0x180;
       } while (tileRowIndex != 8);
       tileRowIndex = 0;
       do {
         upperRowAddress = 0;
         do {
           bitOffset = remainingBits + paletteBitCount;
           currentByte = *bitstreamCursor;
           if (bitOffset - 8 == 0 || (int)bitOffset < 8) {
             if (bitOffset == 8) {
               bitstreamCursor = bitstreamCursor + 1;
             }
             paletteLookupIndex =
                  ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(bitAccumulator & 0x1f);
             remainingBits = 0;
             if (bitOffset != 8) {
               remainingBits = bitOffset;
             }
           }
           else {
             bitstreamCursor = bitstreamCursor + 1;
             paletteLookupIndex =
                  ((uint)*bitstreamCursor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(bitAccumulator & 0x1f) | (uint)(currentByte >> (ulong)(remainingBits & 0x1f));
             remainingBits = bitOffset - 8;
           }
           paletteCacheWrite = (undefined1 *)
                               (*(long *)(decoderStateAddress + 8) +
                               (ulong)*(byte *)(decoderStateAddress + (ulong)paletteLookupIndex + 0x110)
                               * 3)
           ;
           paletteCacheCursor = (undefined1 *)(lowerRowAddress + upperRowAddress);
           upperRowAddress = upperRowAddress + 3;
           *paletteCacheCursor = *paletteCacheWrite;
           paletteCacheCursor[1] = paletteCacheWrite[1];
           paletteCacheCursor[2] = paletteCacheWrite[2];
         } while ((int)upperRowAddress != 0x18);
         tileRowIndex = tileRowIndex + 1;
         lowerRowAddress = lowerRowAddress + 0x180;
       } while (tileRowIndex != 8);
       blockPixelOffset = blockPixelOffset + 0xc00;
       tileRowLimit = tileRowLimit + 0xc00;
       isFirstBlock = false;
     } while (continueProcessing);
     paletteEntryCount = paletteEntryCount + (uint)paletteBitCount * 0x20 + 2;
   }
   else if (*blockDescriptor == '\0') {
     bitAccumulator = 0;
     blockPixelOffset = blockColumn * 0x30 + blockRow * 0x1800;
     paletteBitCount = (&gdivoom_image_bits_table)[paletteBitDepth];
     tileRowLimit = blockPixelOffset + 0x18;
     paletteEntryCount = 8 - paletteBitCount;
     isFirstBlock = true;
     do {
       continueProcessing = isFirstBlock;
       tileRowIndex = 0;
       lowerRowAddress = frameBuffer + tileRowLimit;
       upperRowAddress = frameBuffer + blockPixelOffset;
       do {
         rowBaseAddress = 0;
         do {
           bitOffset = bitAccumulator + paletteBitCount;
           currentByte = *bitstreamCursor;
           if ((int)bitOffset < 9) {
             if (bitOffset == 8) {
               bitstreamCursor = bitstreamCursor + 1;
             }
             paletteLookupIndex =
                  ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(paletteEntryCount & 0x1f);
             bitAccumulator = 0;
             if (bitOffset != 8) {
               bitAccumulator = bitOffset;
             }
           }
           else {
             bitstreamCursor = bitstreamCursor + 1;
             paletteLookupIndex =
                  ((uint)*bitstreamCursor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(paletteEntryCount & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
             bitAccumulator = bitOffset - 8;
           }
           paletteCacheWrite =
                (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                               (ulong)*(byte *)(paletteSource + (ulong)paletteLookupIndex) * 3);
           paletteCacheCursor = (undefined1 *)(upperRowAddress + rowBaseAddress);
           rowBaseAddress = rowBaseAddress + 3;
           *paletteCacheCursor = *paletteCacheWrite;
           paletteCacheCursor[1] = paletteCacheWrite[1];
           paletteCacheCursor[2] = paletteCacheWrite[2];
         } while ((int)rowBaseAddress != 0x18);
         tileRowIndex = tileRowIndex + 1;
         upperRowAddress = upperRowAddress + 0x180;
       } while (tileRowIndex != 8);
       tileRowIndex = 0;
       do {
         upperRowAddress = 0;
         do {
           bitOffset = bitAccumulator + paletteBitCount;
           currentByte = *bitstreamCursor;
           if (bitOffset - 8 == 0 || (int)bitOffset < 8) {
             if (bitOffset == 8) {
               bitstreamCursor = bitstreamCursor + 1;
             }
             paletteLookupIndex =
                  ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(paletteEntryCount & 0x1f);
             bitAccumulator = 0;
             if (bitOffset != 8) {
               bitAccumulator = bitOffset;
             }
           }
           else {
             bitstreamCursor = bitstreamCursor + 1;
             paletteLookupIndex =
                  ((uint)*bitstreamCursor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                  (ulong)(paletteEntryCount & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
             bitAccumulator = bitOffset - 8;
           }
           paletteCacheWrite =
                (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                               (ulong)*(byte *)(paletteSource + (ulong)paletteLookupIndex) * 3);
           paletteCacheCursor = (undefined1 *)(lowerRowAddress + upperRowAddress);
           upperRowAddress = upperRowAddress + 3;
           *paletteCacheCursor = *paletteCacheWrite;
           paletteCacheCursor[1] = paletteCacheWrite[1];
           paletteCacheCursor[2] = paletteCacheWrite[2];
         } while ((int)upperRowAddress != 0x18);
         tileRowIndex = tileRowIndex + 1;
         lowerRowAddress = lowerRowAddress + 0x180;
       } while (tileRowIndex != 8);
       blockPixelOffset = blockPixelOffset + 0xc00;
       tileRowLimit = tileRowLimit + 0xc00;
       isFirstBlock = false;
     } while (continueProcessing);
     paletteEntryCount = (uint)paletteBitCount << 5 | 1;
   }
   else {
     if (paletteEntryCount == 0) {
       paletteCacheIndex = 0;
     }
     else {
       paletteEntryCounter = 0;
       paletteCacheIndex = 0;
       paletteCacheTail = paletteCacheWrite;
       do {
         paletteCacheCursor = paletteCacheTail;
         if (((byte)blockDescriptor[(paletteEntryCounter >> 3 & 0x1fffffff) + 2] >>
              (ulong)((uint)paletteEntryCounter & 7) & 1) != 0) {
           paletteCacheIndex = paletteCacheIndex + 1;
           paletteCacheCursor = paletteCacheTail + 1;
           *paletteCacheTail = *(undefined1 *)(paletteSource + paletteEntryCounter);
         }
         paletteEntryCounter = paletteEntryCounter + 1;
         paletteCacheTail = paletteCacheCursor;
       } while (paletteEntryCount != paletteEntryCounter);
     }
     paletteEntryCount = (paletteEntryCount + 7 >> 3) + 2;
     tileRowLimit = divoom_image_decode_decode_fix_8
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,blockRow << 1,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = tileRowLimit + paletteEntryCount;
     bitAccumulator = blockColumn << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_8
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,blockRow << 1,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     remainingBits = blockRow << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_8
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,remainingBits,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     tileRowLimit = divoom_image_decode_decode_fix_8
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,remainingBits,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
   }
   return paletteEntryCount;
 }
 
 
 uint divoom_image_decode_decode_fix_32
                (long decoderStateAddress,byte *blockDescriptor,long frameBuffer,int blockColumn,
                int blockRow,long paletteSource,int paletteBitDepth)
 
 {
   uint pixelIndex;
   byte frameType;
   byte currentByte;
   uint paletteEntryCount;
   int tileRowIndex;
   int tileRowLimit;
   int tileColumnLimit;
   long lowerRowAddress;
   long upperRowAddress;
   uint paletteLookupIndex;
   short paletteCacheIndex;
   byte *bitstreamCursor;
   ulong paletteEntryCounter;
   uint bitOffset;
   ulong paletteCursorIndex;
   undefined1 *paletteCacheCursor;
   uint bitAccumulator;
   int blockPixelOffset;
   int blockPixelStride;
   undefined1 *paletteCacheWrite;
   undefined1 *paletteCacheTail;
   
   frameType = *blockDescriptor;
   paletteEntryCount = (uint)frameType;
   bitstreamCursor = blockDescriptor + 1;
   paletteCacheWrite = (undefined1 *)(decoderStateAddress + 0x210);
   paletteLookupIndex = 0x100;
   if (*bitstreamCursor != 0) {
     paletteLookupIndex = (uint)*bitstreamCursor;
   }
   if (frameType == 2) {
     if (paletteLookupIndex == 0) {
       paletteCursorIndex = 0;
     }
     else {
       paletteEntryCounter = 0;
       paletteCursorIndex = 0;
       do {
         paletteCacheTail = paletteCacheWrite;
         if ((blockDescriptor[(paletteEntryCounter >> 3 & 0x1fffffff) + 2] >>
              (ulong)((uint)paletteEntryCounter & 7) & 1) != 0) {
           paletteCursorIndex = (ulong)((int)paletteCursorIndex + 1);
           paletteCacheTail = paletteCacheWrite + 1;
           *paletteCacheWrite = *(undefined1 *)(paletteSource + paletteEntryCounter);
         }
         paletteEntryCounter = paletteEntryCounter + 1;
         paletteCacheWrite = paletteCacheTail;
       } while (paletteLookupIndex != paletteEntryCounter);
     }
     bitAccumulator = 0;
     paletteEntryCount = paletteLookupIndex + 7 >> 3;
     frameType = (&gdivoom_image_bits_table)[paletteCursorIndex & 0xffff];
     blockPixelOffset = blockColumn * 0x60 + blockRow * 0x3000;
     blockDescriptor = blockDescriptor + (ulong)paletteEntryCount + 2;
     paletteLookupIndex = 8 - frameType;
     do {
       tileRowLimit = 0;
       tileRowIndex = blockPixelOffset;
       do {
         tileColumnLimit = 0;
         lowerRowAddress = frameBuffer + tileRowIndex;
         do {
           upperRowAddress = 0;
           do {
             bitOffset = bitAccumulator + frameType;
             currentByte = *blockDescriptor;
             if ((int)bitOffset < 9) {
               if (bitOffset == 8) {
                 blockDescriptor = blockDescriptor + 1;
               }
               paletteEntryCount =
                    ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f);
               bitAccumulator = 0;
               if (bitOffset != 8) {
                 bitAccumulator = bitOffset;
               }
             }
             else {
               blockDescriptor = blockDescriptor + 1;
               paletteEntryCount =
                    ((uint)*blockDescriptor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
               bitAccumulator = bitOffset - 8;
             }
             paletteCacheWrite =
                  (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                                 (ulong)*(byte *)(decoderStateAddress + (ulong)paletteEntryCount + 0x210) *
                                 3);
             paletteCacheCursor = (undefined1 *)(lowerRowAddress + upperRowAddress);
             upperRowAddress = upperRowAddress + 3;
             *paletteCacheCursor = *paletteCacheWrite;
             paletteCacheCursor[1] = paletteCacheWrite[1];
             paletteCacheCursor[2] = paletteCacheWrite[2];
           } while ((int)upperRowAddress != 0x18);
           tileColumnLimit = tileColumnLimit + 1;
           lowerRowAddress = lowerRowAddress + 0x180;
         } while (tileColumnLimit != 8);
         tileRowLimit = tileRowLimit + 1;
         tileRowIndex = tileRowIndex + 0x18;
       } while (tileRowLimit != 4);
       blockPixelOffset = blockPixelOffset + 0xc00;
     } while (blockPixelOffset != blockColumn * 0x60 + blockRow * 0x3000 + 0x3000);
     paletteEntryCount = (paletteEntryCount | (uint)frameType << 7) + 2;
   }
   else if (frameType == 0) {
     bitAccumulator = 0;
     blockPixelOffset = blockColumn * 0x60 + blockRow * 0x3000;
     frameType = (&gdivoom_image_bits_table)[paletteBitDepth];
     paletteLookupIndex = 8 - frameType;
     do {
       tileRowLimit = 0;
       tileRowIndex = blockPixelOffset;
       do {
         tileColumnLimit = 0;
         lowerRowAddress = frameBuffer + tileRowIndex;
         do {
           upperRowAddress = 0;
           do {
             bitOffset = bitAccumulator + frameType;
             currentByte = *bitstreamCursor;
             if ((int)bitOffset < 9) {
               if (bitOffset == 8) {
                 bitstreamCursor = bitstreamCursor + 1;
               }
               paletteEntryCount =
                    ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f);
               bitAccumulator = 0;
               if (bitOffset != 8) {
                 bitAccumulator = bitOffset;
               }
             }
             else {
               bitstreamCursor = bitstreamCursor + 1;
               paletteEntryCount =
                    ((uint)*bitstreamCursor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
               bitAccumulator = bitOffset - 8;
             }
             paletteCacheWrite =
                  (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                                 (ulong)*(byte *)(paletteSource + (ulong)paletteEntryCount) * 3);
             paletteCacheCursor = (undefined1 *)(lowerRowAddress + upperRowAddress);
             upperRowAddress = upperRowAddress + 3;
             *paletteCacheCursor = *paletteCacheWrite;
             paletteCacheCursor[1] = paletteCacheWrite[1];
             paletteCacheCursor[2] = paletteCacheWrite[2];
           } while ((int)upperRowAddress != 0x18);
           tileColumnLimit = tileColumnLimit + 1;
           lowerRowAddress = lowerRowAddress + 0x180;
         } while (tileColumnLimit != 8);
         tileRowLimit = tileRowLimit + 1;
         tileRowIndex = tileRowIndex + 0x18;
       } while (tileRowLimit != 4);
       paletteEntryCount = paletteEntryCount + 1;
       blockPixelOffset = blockPixelOffset + 0xc00;
     } while (paletteEntryCount != 4);
     paletteEntryCount = (uint)frameType << 7 | 1;
   }
   else {
     if (paletteLookupIndex == 0) {
       paletteCacheIndex = 0;
     }
     else {
       paletteCursorIndex = 0;
       paletteCacheIndex = 0;
       paletteCacheTail = paletteCacheWrite;
       do {
         paletteCacheCursor = paletteCacheTail;
         if ((blockDescriptor[(paletteCursorIndex >> 3 & 0x1fffffff) + 2] >>
              (ulong)((uint)paletteCursorIndex & 7) & 1) != 0) {
           paletteCacheIndex = paletteCacheIndex + 1;
           paletteCacheCursor = paletteCacheTail + 1;
           *paletteCacheTail = *(undefined1 *)(paletteSource + paletteCursorIndex);
         }
         paletteCursorIndex = paletteCursorIndex + 1;
         paletteCacheTail = paletteCacheCursor;
       } while (paletteLookupIndex != paletteCursorIndex);
     }
     paletteEntryCount = (paletteLookupIndex + 7 >> 3) + 2;
     tileRowLimit = divoom_image_decode_decode_fix_16
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,blockRow << 1,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = tileRowLimit + paletteEntryCount;
     bitAccumulator = blockColumn << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_16
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,blockRow << 1,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     paletteLookupIndex = blockRow << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_16
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,paletteLookupIndex,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     tileRowLimit = divoom_image_decode_decode_fix_16
                               (decoderStateAddress,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,paletteLookupIndex,paletteCacheWrite,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
   }
   return paletteEntryCount;
 }
 
 
 uint divoom_image_decode_decode_fix_64
                (ushort *decoderState,byte *blockDescriptor,long frameBuffer,int blockColumn,
                int blockRow)
 
 {
   uint pixelIndex;
   undefined1 *paletteCacheCursor;
   undefined1 *paletteCacheWrite;
   byte frameType;
   byte currentByte;
   uint paletteEntryCount;
   int tileRowIndex;
   int tileRowLimit;
   int tileColumnLimit;
   long lowerRowAddress;
   long upperRowAddress;
   uint paletteLookupIndex;
   short paletteCacheIndex;
   byte *bitstreamCursor;
   uint paletteEntryCounter;
   ulong paletteCursorIndex;
   ushort *paletteCacheTail;
   uint bitAccumulator;
   int blockPixelOffset;
   int blockPixelStride;
   ushort *paletteCacheWrite16;
   ushort *paletteCacheCursor16;
   
   frameType = *blockDescriptor;
   paletteEntryCount = (uint)frameType;
   bitstreamCursor = blockDescriptor + 1;
   paletteCacheWrite16 = decoderState + 0x188;
   paletteLookupIndex = 0x100;
   if (*bitstreamCursor != 0) {
     paletteLookupIndex = (uint)*bitstreamCursor;
   }
   if (frameType == 2) {
     paletteCursorIndex = 0;
     if (paletteLookupIndex != 0) {
       paletteEntryCounter = 0;
       do {
         paletteCacheCursor16 = paletteCacheWrite16;
         if ((blockDescriptor[(ulong)(paletteEntryCounter >> 3) + 2] >>
              (ulong)(paletteEntryCounter & 7) & 1) != 0) {
           paletteCursorIndex = (ulong)((int)paletteCursorIndex + 1);
           paletteCacheCursor16 = (ushort *)((long)paletteCacheWrite16 + 1);
           *(char *)paletteCacheWrite16 = (char)paletteEntryCounter;
         }
         paletteEntryCounter = paletteEntryCounter + 1;
         paletteCacheWrite16 = paletteCacheCursor16;
       } while (paletteLookupIndex != paletteEntryCounter);
     }
     bitAccumulator = 0;
     paletteEntryCount = paletteLookupIndex + 7 >> 3;
     frameType = (&gdivoom_image_bits_table)[paletteCursorIndex & 0xffff];
     blockPixelOffset = blockColumn * 0xc0 + blockRow * 0x6000;
     blockDescriptor = blockDescriptor + (ulong)paletteEntryCount + 2;
     paletteLookupIndex = 8 - frameType;
     do {
       tileRowLimit = 0;
       tileRowIndex = blockPixelOffset;
       do {
         tileColumnLimit = 0;
         lowerRowAddress = frameBuffer + tileRowIndex;
         do {
           upperRowAddress = 0;
           do {
             pixelIndex = bitAccumulator + frameType;
             currentByte = *blockDescriptor;
             if ((int)pixelIndex < 9) {
               if (pixelIndex == 8) {
                 blockDescriptor = blockDescriptor + 1;
               }
               paletteEntryCount =
                    ((uint)currentByte << (ulong)(8 - pixelIndex & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f);
               bitAccumulator = 0;
               if (pixelIndex != 8) {
                 bitAccumulator = pixelIndex;
               }
             }
             else {
               blockDescriptor = blockDescriptor + 1;
               paletteEntryCount =
                    ((uint)*blockDescriptor << (ulong)(0x10 - pixelIndex & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
               bitAccumulator = pixelIndex - 8;
             }
             paletteCacheCursor =
                  (undefined1 *)(*(long *)(decoderState + 4) +
                                 (ulong)*(byte *)((long)decoderState + (ulong)paletteEntryCount + 0x310) *
                                 3);
             paletteCacheWrite = (undefined1 *)(lowerRowAddress + upperRowAddress);
             upperRowAddress = upperRowAddress + 3;
             *paletteCacheWrite = *paletteCacheCursor;
             paletteCacheWrite[1] = paletteCacheCursor[1];
             paletteCacheWrite[2] = paletteCacheCursor[2];
           } while ((int)upperRowAddress != 0x18);
           tileColumnLimit = tileColumnLimit + 1;
           lowerRowAddress = lowerRowAddress + 0x180;
         } while (tileColumnLimit != 8);
         tileRowLimit = tileRowLimit + 1;
         tileRowIndex = tileRowIndex + 0x18;
       } while (tileRowLimit != 8);
       blockPixelOffset = blockPixelOffset + 0xc00;
     } while (blockPixelOffset != blockColumn * 0xc0 + blockRow * 0x6000 + 0x6000);
     paletteEntryCount = (paletteEntryCount | (uint)frameType << 9) + 2;
   }
   else if (frameType == 0) {
     bitAccumulator = 0;
     frameType = (&gdivoom_image_bits_table)[*decoderState];
     blockPixelOffset = blockColumn * 0xc0 + blockRow * 0x6000;
     paletteLookupIndex = 8 - frameType;
     do {
       tileRowLimit = 0;
       tileRowIndex = blockPixelOffset;
       do {
         tileColumnLimit = 0;
         lowerRowAddress = frameBuffer + tileRowIndex;
         do {
           upperRowAddress = 0;
           do {
             pixelIndex = bitAccumulator + frameType;
             currentByte = *bitstreamCursor;
             if ((int)pixelIndex < 9) {
               if (pixelIndex == 8) {
                 bitstreamCursor = bitstreamCursor + 1;
               }
               paletteEntryCount =
                    ((uint)currentByte << (ulong)(8 - pixelIndex & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f);
               bitAccumulator = 0;
               if (pixelIndex != 8) {
                 bitAccumulator = pixelIndex;
               }
             }
             else {
               bitstreamCursor = bitstreamCursor + 1;
               paletteEntryCount =
                    ((uint)*bitstreamCursor << (ulong)(0x10 - pixelIndex & 0x1f) & 0xff) >>
                    (ulong)(paletteLookupIndex & 0x1f) | (uint)(currentByte >> (ulong)(bitAccumulator & 0x1f));
               bitAccumulator = pixelIndex - 8;
             }
             paletteCacheCursor = (undefined1 *)(*(long *)(decoderState + 4) + (ulong)(paletteEntryCount * 3));
             paletteCacheWrite = (undefined1 *)(lowerRowAddress + upperRowAddress);
             upperRowAddress = upperRowAddress + 3;
             *paletteCacheWrite = *paletteCacheCursor;
             paletteCacheWrite[1] = paletteCacheCursor[1];
             paletteCacheWrite[2] = paletteCacheCursor[2];
           } while ((int)upperRowAddress != 0x18);
           tileColumnLimit = tileColumnLimit + 1;
           lowerRowAddress = lowerRowAddress + 0x180;
         } while (tileColumnLimit != 8);
         tileRowLimit = tileRowLimit + 1;
         tileRowIndex = tileRowIndex + 0x18;
       } while (tileRowLimit != 8);
       paletteEntryCount = paletteEntryCount + 1;
       blockPixelOffset = blockPixelOffset + 0xc00;
     } while (paletteEntryCount != 8);
     paletteEntryCount = (uint)frameType << 9 | 1;
   }
   else {
     paletteCacheIndex = 0;
     if (paletteLookupIndex != 0) {
       paletteEntryCounter = 0;
       paletteCacheTail = paletteCacheWrite16;
       do {
         paletteCacheCursor16 = paletteCacheTail;
         if ((blockDescriptor[(ulong)(paletteEntryCounter >> 3) + 2] >>
              (ulong)(paletteEntryCounter & 7) & 1) != 0) {
           paletteCacheIndex = paletteCacheIndex + 1;
           paletteCacheCursor16 = (ushort *)((long)paletteCacheTail + 1);
           *(char *)paletteCacheTail = (char)paletteEntryCounter;
         }
         paletteEntryCounter = paletteEntryCounter + 1;
         paletteCacheTail = paletteCacheCursor16;
       } while (paletteLookupIndex != paletteEntryCounter);
     }
     paletteEntryCount = (paletteLookupIndex + 7 >> 3) + 2;
     tileRowLimit = divoom_image_decode_decode_fix_32
                               (decoderState,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,blockRow << 1,paletteCacheWrite16,paletteCacheIndex);
     paletteEntryCount = tileRowLimit + paletteEntryCount;
     bitAccumulator = blockColumn << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_32
                               (decoderState,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,blockRow << 1,paletteCacheWrite16,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     paletteLookupIndex = blockRow << 1 | 1;
     tileRowLimit = divoom_image_decode_decode_fix_32
                               (decoderState,blockDescriptor + paletteEntryCount,frameBuffer,
                                blockColumn << 1,paletteLookupIndex,paletteCacheWrite16,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
     tileRowLimit = divoom_image_decode_decode_fix_32
                               (decoderState,blockDescriptor + paletteEntryCount,frameBuffer,
                                bitAccumulator,paletteLookupIndex,paletteCacheWrite16,paletteCacheIndex);
     paletteEntryCount = paletteEntryCount + tileRowLimit;
   }
   return paletteEntryCount;
 }
 
 
 uint divoom_image_decode_decode_fix_8
                (long decoderStateAddress,byte *blockDescriptor,long frameBuffer,int blockColumn,
                int blockRow,long paletteSource,int paletteBitDepth)
 
 {
   byte currentByte;
   byte flagByte;
   uint paletteEntryCount;
   int blockPixelStride;
   uint paletteLookupIndex;
   uint bitAccumulator;
   ulong paletteCursorIndex;
   int tileRowLimit;
   ulong tilePixelOffset;
   uint pixelIndex;
   undefined1 *paletteCacheCursor;
   undefined1 *paletteCacheWrite;
   uint bitOffset;
   long rowAddress;
   
   flagByte = *blockDescriptor;
   blockPixelStride = (blockRow * 0x400 + blockColumn * 8) * 3;
   if ((char)flagByte < '\0') {
     if ((flagByte & 0x7f) == 0) {
       paletteCursorIndex = 0;
     }
     else {
       paletteCursorIndex = 0;
       paletteEntryCount = 0;
       paletteCacheCursor = (undefined1 *)(decoderStateAddress + 0x10);
       do {
         paletteCacheWrite = paletteCacheCursor;
         if ((blockDescriptor[(paletteCursorIndex >> 3 & 0x1fffffff) + 1] >>
              (ulong)((uint)paletteCursorIndex & 7) & 1) != 0) {
           paletteEntryCount = (ulong)((int)paletteEntryCount + 1);
           paletteCacheWrite = paletteCacheCursor + 1;
           *paletteCacheCursor = *(undefined1 *)(paletteSource + paletteCursorIndex);
         }
         paletteCursorIndex = paletteCursorIndex + 1;
         paletteCacheCursor = paletteCacheWrite;
       } while ((flagByte & 0x7f) != paletteCursorIndex);
     }
     paletteLookupIndex = 0;
     tileRowLimit = 0;
     paletteEntryCount = ((flagByte & 0x7f) + 7 >> 3) + 1;
     blockDescriptor = blockDescriptor + paletteEntryCount;
     frameBuffer = frameBuffer + blockPixelStride;
     flagByte = (&gdivoom_image_bits_table)[paletteEntryCount & 0xff];
     bitAccumulator = 8 - flagByte;
     do {
       rowAddress = 0;
       do {
         bitOffset = paletteLookupIndex + flagByte;
         currentByte = *blockDescriptor;
         if ((int)bitOffset < 9) {
           if (bitOffset == 8) {
             blockDescriptor = blockDescriptor + 1;
           }
           pixelIndex =
                ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                (ulong)(bitAccumulator & 0x1f);
           paletteLookupIndex = 0;
           if (bitOffset != 8) {
             paletteLookupIndex = bitOffset;
           }
         }
         else {
           blockDescriptor = blockDescriptor + 1;
           pixelIndex =
                ((uint)*blockDescriptor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                (ulong)(bitAccumulator & 0x1f) | (uint)(currentByte >> (ulong)(paletteLookupIndex & 0x1f));
           paletteLookupIndex = bitOffset - 8;
         }
         paletteCacheCursor = (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                                             (ulong)*(byte *)(decoderStateAddress + (ulong)pixelIndex + 0x10) *
                                             3);
         paletteCacheWrite = (undefined1 *)(frameBuffer + rowAddress);
         rowAddress = rowAddress + 3;
         *paletteCacheWrite = *paletteCacheCursor;
         paletteCacheWrite[1] = paletteCacheCursor[1];
         paletteCacheWrite[2] = paletteCacheCursor[2];
       } while ((int)rowAddress != 0x18);
       tileRowLimit = tileRowLimit + 1;
       frameBuffer = frameBuffer + 0x180;
     } while (tileRowLimit != 8);
     return paletteEntryCount + (uint)flagByte * 8;
   }
   paletteLookupIndex = 0;
   tileRowLimit = 0;
   blockDescriptor = blockDescriptor + 1;
   frameBuffer = frameBuffer + blockPixelStride;
   flagByte = (&gdivoom_image_bits_table)[paletteBitDepth];
   paletteEntryCount = 8 - flagByte;
   do {
     rowAddress = 0;
     do {
       bitOffset = paletteLookupIndex + flagByte;
       currentByte = *blockDescriptor;
       if ((int)bitOffset < 9) {
         if (bitOffset == 8) {
           blockDescriptor = blockDescriptor + 1;
         }
         pixelIndex = ((uint)currentByte << (ulong)(8 - bitOffset & 0x1f) & 0xff) >>
                      (ulong)(paletteEntryCount & 0x1f);
         paletteLookupIndex = 0;
         if (bitOffset != 8) {
           paletteLookupIndex = bitOffset;
         }
       }
       else {
         blockDescriptor = blockDescriptor + 1;
         pixelIndex = ((uint)*blockDescriptor << (ulong)(0x10 - bitOffset & 0x1f) & 0xff) >>
                      (ulong)(paletteEntryCount & 0x1f) | (uint)(currentByte >> (ulong)(paletteLookupIndex & 0x1f));
         paletteLookupIndex = bitOffset - 8;
       }
       paletteCacheCursor =
            (undefined1 *)(*(long *)(decoderStateAddress + 8) +
                           (ulong)*(byte *)(paletteSource + (ulong)pixelIndex) * 3);
       paletteCacheWrite = (undefined1 *)(frameBuffer + rowAddress);
       rowAddress = rowAddress + 3;
       *paletteCacheWrite = *paletteCacheCursor;
       paletteCacheWrite[1] = paletteCacheCursor[1];
       paletteCacheWrite[2] = paletteCacheCursor[2];
     } while ((int)rowAddress != 0x18);
     tileRowLimit = tileRowLimit + 1;
     frameBuffer = frameBuffer + 0x180;
   } while (tileRowLimit != 8);
   return (uint)flagByte << 3 | 1;
 }
 
 
 int divoom_image_decode_decode_fix_absolute_index_from_map
               (long paletteSource,long bitfieldMap,uint entryCount,undefined1 *paletteCache)
 
 {
   int entriesCopied;
   undefined1 *paletteCachePtr;
   ulong entryIndex;
   
   if (0 < (int)entryCount) {
     entryIndex = 0;
     entriesCopied = 0;
     do {
       paletteCachePtr = paletteCache;
       if ((*(byte *)(bitfieldMap + (entryIndex >> 3 & 0x1fffffff)) >> (ulong)((uint)entryIndex & 7) & 1) != 0) {
         entriesCopied = entriesCopied + 1;
         paletteCachePtr = paletteCache + 1;
         *paletteCache = *(undefined1 *)(paletteSource + entryIndex);
       }
       entryIndex = entryIndex + 1;
       paletteCache = paletteCachePtr;
     } while (entryCount != entryIndex);
     return entriesCopied;
   }
   return 0;
 }
 
 
 int divoom_image_decode_decode_fix_get_index_from_map(long bitfieldMap,uint entryCount,
                                                      undefined1 *indexCache)
 
 {
   undefined1 *indexCachePtr;
   int indicesCopied;
   uint entryIndex;
   
   if (0 < (int)entryCount) {
     indicesCopied = 0;
     entryIndex = 0;
     do {
       indexCachePtr = indexCache;
       if ((*(byte *)(bitfieldMap + (ulong)(entryIndex >> 3)) >> (ulong)(entryIndex & 7) & 1) != 0) {
         indicesCopied = indicesCopied + 1;
         indexCachePtr = indexCache + 1;
         *indexCache = (char)entryIndex;
       }
       entryIndex = entryIndex + 1;
       indexCache = indexCachePtr;
     } while (entryCount != entryIndex);
     return indicesCopied;
   }
   return 0;
 }
 
 
 int divoom_image_decode_decode_get_pic_num(long frameBase,uint encodedLength)
 
 {
   int picCount;
   uint frameOffset;
   
   picCount = 0;
   if ((frameBase != 0) && (encodedLength != 0)) {
     frameOffset = 0;
     picCount = 0;
     do {
       picCount = picCount + 1;
       frameOffset = *(ushort *)(frameBase + (ulong)frameOffset + 1) + frameOffset;
     } while (frameOffset < encodedLength);
   }
   return picCount;
 }
 
 
 undefined1 divoom_image_decode_decode_get_type(long decoderStateAddress)
 
 {
   if (*(uint *)(decoderStateAddress + 0xc) < *(uint *)(decoderStateAddress + 4)) {
     return *(undefined1 *)(*(long *)(decoderStateAddress + 0x10) +
                           (ulong)(*(uint *)(decoderStateAddress + 0xc) + 5));
   }
   printf("err: %d!\n",0x18f3);
   return 6;
 }
 
 
 uint divoom_image_decode_decode_handle
                (long decoderStateAddress,long encodedStream,long outputPixelBuffer,
                undefined8 userContext,uint requestedFormat)
 
 {
   uint pixelIndex;
   long destinationBlockAddress;
   undefined1 *paletteCacheCursor;
   undefined1 *paletteCacheWrite;
   uint requestedFormatByte;
   uint rowIndex;
   undefined2 rgb565Pair;
   ushort tileOffset;
   uint decodeStatus;
   char *messageFormat;
   undefined8 messageId;
   ulong tileIndex;
   short paletteWriteIndex;
   uint columnIndex;
   uint frameCount;
   int decodedFrameIndex;
   ulong frameIndex;
   int formatStride;
   
   frameCount = 0;
   if (((decoderStateAddress != 0) && (encodedStream != 0)) && (outputPixelBuffer != 0)) {
     requestedFormatByte = requestedFormat & 0xff;
     if (requestedFormatByte == 0x10) {
       formatStride = 0x300;
     }
     else if (requestedFormatByte == 0x40) {
       formatStride = 0x3000;
     }
     else {
       if (requestedFormatByte != 0x20) {
         return 0;
       }
       formatStride = 0xc00;
     }
     frameCount = (uint)*(ushort *)(encodedStream + 1);
     if (*(void **)(decoderStateAddress + 0x18) != (void *)0x0) {
       free(*(void **)(decoderStateAddress + 0x18));
       *(undefined8 *)(decoderStateAddress + 0x18) = 0;
     }
     *(uint *)(decoderStateAddress + 4) = frameCount;
     *(undefined4 *)(decoderStateAddress + 0xc) = 0;
     *(long *)(decoderStateAddress + 0x10) = encodedStream;
     if (frameCount != 0) {
       decodedFrameIndex = 0;
       decodeStatus = 0;
       do {
         if (*(char *)(encodedStream + (ulong)decodeStatus) != -0x56) {
           frameCount = -decodedFrameIndex;
           if (decodedFrameIndex == 0) {
             return frameCount;
           }
           goto LAB_0025fb3c;
         }
         decodedFrameIndex = decodedFrameIndex + -1;
         decodeStatus = *(ushort *)(encodedStream + (ulong)decodeStatus + 1) + decodeStatus;
       } while (decodeStatus < frameCount);
       frameCount = -decodedFrameIndex;
 LAB_0025fb3c:
       frameIndex = 0;
       do {
         decodedFrameIndex = (int)frameIndex;
         decodeStatus = divoom_image_decode_decode_pic
                                (decoderStateAddress,outputPixelBuffer +
                                                      (ulong)(uint)(formatStride * decodedFrameIndex),
                                 userContext);
         tileIndex = (ulong)(decodeStatus & 0xff);
         if ((requestedFormat & 0xff) < (decodeStatus & 0xff)) {
           messageId = 0x16a9;
           messageFormat = "pic size err: %d, %d, %d!\n";
           frameIndex = (ulong)requestedFormatByte;
 LAB_0025fd0c:
           printf(messageFormat,messageId,tileIndex,frameIndex);
           return frameCount;
         }
         if ((decodeStatus & 0xff) == 0) {
           messageId = 0x16ae;
           messageFormat = "pic decode err: %d, %d, %d!\n";
           tileIndex = 0;
           frameIndex = frameIndex & 0xffffffff;
           goto LAB_0025fd0c;
         }
         if ((decodeStatus & 0xff) < (requestedFormat & 0xff)) {
           if ((requestedFormat & 0xff) == 0x40) {
             destinationBlockAddress = outputPixelBuffer + (ulong)(uint)(decodedFrameIndex * 0x3000);
             if ((decodeStatus & 0xff) == 0x10) {
               paletteWriteIndex = 0xfff;
               decodeStatus = 0x3f;
               do {
                 columnIndex = 0x3f;
                 do {
                   rowIndex = columnIndex & 0xffff;
                   columnIndex = columnIndex - 1;
                   pixelIndex = (decodeStatus & 0x3ffffffc) * 4 + (rowIndex >> 2);
                   tileOffset = paletteWriteIndex * 3;
                   paletteCacheWrite = (undefined1 *)(destinationBlockAddress +
                                                      ((ulong)pixelIndex & 0xffff) +
                                                      (ulong)(ushort)pixelIndex * 2);
                   paletteWriteIndex = paletteWriteIndex + -1;
                   paletteCacheCursor = (undefined1 *)(destinationBlockAddress + (ulong)tileOffset);
                   rgb565Pair = *(undefined2 *)(paletteCacheWrite + 1);
                   *paletteCacheCursor = *paletteCacheWrite;
                   *(undefined2 *)(paletteCacheCursor + 1) = rgb565Pair;
                 } while (rowIndex != 0);
                 columnIndex = decodeStatus & 0xffff;
                 decodeStatus = decodeStatus - 1;
               } while (columnIndex != 0);
             }
             else {
               paletteWriteIndex = 0xfff;
               decodeStatus = 0x3f;
               do {
                 columnIndex = 0x3f;
                 do {
                   rowIndex = columnIndex & 0xffff;
                   columnIndex = columnIndex - 1;
                   pixelIndex = (decodeStatus & 0xffffffe) * 0x10 + (rowIndex >> 1);
                   tileOffset = paletteWriteIndex * 3;
                   paletteCacheWrite = (undefined1 *)(destinationBlockAddress +
                                                      ((ulong)pixelIndex & 0xffff) +
                                                      (ulong)(ushort)pixelIndex * 2);
                   paletteWriteIndex = paletteWriteIndex + -1;
                   paletteCacheCursor = (undefined1 *)(destinationBlockAddress + (ulong)tileOffset);
                   rgb565Pair = *(undefined2 *)(paletteCacheWrite + 1);
                   *paletteCacheCursor = *paletteCacheWrite;
                   *(undefined2 *)(paletteCacheCursor + 1) = rgb565Pair;
                 } while (rowIndex != 0);
                 columnIndex = decodeStatus & 0xffff;
                 decodeStatus = decodeStatus - 1;
               } while (columnIndex != 0);
             }
           }
           else if ((requestedFormat & 0xff) == 0x20) {
             tileIndex = 0x3ff;
             destinationBlockAddress = outputPixelBuffer + (ulong)(uint)(decodedFrameIndex * 0xc00);
             decodeStatus = 0x1f;
             do {
               columnIndex = 0x1f;
               do {
                 rowIndex = columnIndex & 0xffff;
                 columnIndex = columnIndex - 1;
                 pixelIndex = (decodeStatus & 0x1ffffffe) * 8 + (rowIndex >> 1);
                 paletteCacheCursor = (undefined1 *)(destinationBlockAddress +
                                                     ((ulong)pixelIndex & 0xffff) +
                                                     (ulong)(ushort)pixelIndex * 2);
                 paletteCacheWrite = (undefined1 *)(destinationBlockAddress + (tileIndex & 0xffff) +
                                                    (tileIndex & 0xffff) * 2);
                 tileIndex = (ulong)((int)tileIndex - 1);
                 rgb565Pair = *(undefined2 *)(paletteCacheCursor + 1);
                 *paletteCacheWrite = *paletteCacheCursor;
                 *(undefined2 *)(paletteCacheWrite + 1) = rgb565Pair;
               } while (rowIndex != 0);
               columnIndex = decodeStatus & 0xffff;
               decodeStatus = decodeStatus - 1;
             } while (columnIndex != 0);
           }
         }
         frameIndex = frameIndex + 1;
       } while (frameIndex != frameCount);
     }
   }
   return frameCount;
 }
 
 
 void divoom_image_decode_decode_large_pic(undefined8 userContext,long frameBuffer)
 
 {
   uint sourcePixelIndex;
   undefined1 *sourcePixelPtr;
   undefined1 *destPixelPtr;
   uint columnIndex;
   undefined2 rgb565Pair;
   short rowIndexCheck;
   ulong destPixelIndex;
   uint rowIndex;
   uint columnCounter;
   
   destPixelIndex = 0x3ff;
   rowIndex = 0x1f;
   do {
     columnCounter = 0x1f;
     do {
       columnIndex = columnCounter & 0xffff;
       columnCounter = columnCounter - 1;
       sourcePixelIndex = (rowIndex & 0x1ffffffe) * 8 + (columnIndex >> 1);
       sourcePixelPtr = (undefined1 *)(frameBuffer + ((ulong)sourcePixelIndex & 0xffff) + (ulong)(ushort)sourcePixelIndex * 2);
       destPixelPtr = (undefined1 *)(frameBuffer + (destPixelIndex & 0xffff) + (destPixelIndex & 0xffff) * 2);
       destPixelIndex = (ulong)((int)destPixelIndex - 1);
       rgb565Pair = *(undefined2 *)(sourcePixelPtr + 1);
       *destPixelPtr = *sourcePixelPtr;
       *(undefined2 *)(destPixelPtr + 1) = rgb565Pair;
     } while (columnIndex != 0);
     rowIndexCheck = (short)rowIndex;
     rowIndex = rowIndex - 1;
   } while (0 < rowIndexCheck);
   return;
 }
 
 
 void divoom_image_decode_decode_large_pic_64(undefined8 userContext,long frameBuffer,char formatByte)
 
 {
   undefined1 *destPixelPtr;
   uint sourcePixelIndex;
   undefined1 *sourcePixelPtr;
   uint columnIndex;
   undefined2 rgb565Pair;
   short rowIndexCheck;
   ushort destPixelOffset;
   short destPixelIndex;
   uint rowIndex;
   uint columnCounter;
   
   if (formatByte == '\x10') {
     destPixelIndex = 0xfff;
     rowIndex = 0x3f;
     do {
       columnCounter = 0x3f;
       do {
         columnIndex = columnCounter & 0xffff;
         columnCounter = columnCounter - 1;
         sourcePixelIndex = (rowIndex & 0x3ffffffc) * 4 + (columnIndex >> 2);
         destPixelOffset = destPixelIndex * 3;
         sourcePixelPtr = (undefined1 *)(frameBuffer + ((ulong)sourcePixelIndex & 0xffff) + (ulong)(ushort)sourcePixelIndex * 2);
         destPixelIndex = destPixelIndex + -1;
         destPixelPtr = (undefined1 *)(frameBuffer + (ulong)destPixelOffset);
         rgb565Pair = *(undefined2 *)(sourcePixelPtr + 1);
         *destPixelPtr = *sourcePixelPtr;
         *(undefined2 *)(destPixelPtr + 1) = rgb565Pair;
       } while (columnIndex != 0);
       rowIndexCheck = (short)rowIndex;
       rowIndex = rowIndex - 1;
     } while (0 < rowIndexCheck);
   }
   else {
     destPixelIndex = 0xfff;
     rowIndex = 0x3f;
     do {
       columnCounter = 0x3f;
       do {
         columnIndex = columnCounter & 0xffff;
         columnCounter = columnCounter - 1;
         sourcePixelIndex = (rowIndex & 0xffffffe) * 0x10 + (columnIndex >> 1);
         destPixelOffset = destPixelIndex * 3;
         sourcePixelPtr = (undefined1 *)(frameBuffer + ((ulong)sourcePixelIndex & 0xffff) + (ulong)(ushort)sourcePixelIndex * 2);
         destPixelIndex = destPixelIndex + -1;
         destPixelPtr = (undefined1 *)(frameBuffer + (ulong)destPixelOffset);
         rgb565Pair = *(undefined2 *)(sourcePixelPtr + 1);
         *destPixelPtr = *sourcePixelPtr;
         *(undefined2 *)(destPixelPtr + 1) = rgb565Pair;
       } while (columnIndex != 0);
       rowIndexCheck = (short)rowIndex;
       rowIndex = rowIndex - 1;
     } while (0 < rowIndexCheck);
   }
   return;
 }
 
 
 undefined8
 divoom_image_decode_decode_one
           (ushort *decoderState,char *frameData,long pixelBuffer,int *bytesConsumed,
           undefined2 *frameDelay)
 
 {
   undefined1 *outputPixelPtr;
   undefined1 *paletteEntryPtr;
   void *paletteBufferPtr;
   ushort *paletteWriteStart;
   ushort *paletteWriteEnd;
   uint bitOffset;
   char paletteByte1;
   byte frameFormatType;
   char paletteByte2;
   ushort currentPaletteCount;
   undefined1 overflowCheck [16];
   short newPaletteCount;
   bool hasOverflow;
   void *existingPaletteBuffer;
   char *errorMessage;
   char *paletteDataStart;
   undefined8 *newPaletteBuffer;
   undefined8 errorCode;
   ulong paletteEntryCount;
   int paletteCopyOffset;
   long pixelBufferOffset;
   uint paletteEntryCounter;
   ulong currentPaletteCountUlong;
   undefined8 *paletteWriteCursor;
   ulong alignedPaletteSize;
   ushort *paletteDataPtr;
   char *paletteReadCursor;
   ulong bitstreamOffset;
   uint paletteIndex;
   undefined8 paletteChunk0;
   undefined8 paletteChunk1;
   undefined8 paletteChunk2;
   undefined8 paletteChunk3;
   
   if (frameData == (char *)0x0) {
     errorCode = 0x1578;
     errorMessage = "err: %d!\n";
 LAB_0025edd0:
     printf(errorMessage,errorCode);
     return 0;
   }
   if (*frameData != -0x56) {
     errorCode = 0x157d;
     errorMessage = "image err err: %d!\n";
     goto LAB_0025edd0;
   }
   frameFormatType = frameData[5];
   if (1 < frameFormatType) {
     errorCode = 0x1582;
     errorMessage = "image size err: %d!\n";
     goto LAB_0025edd0;
   }
   if (frameDelay != (undefined2 *)0x0) {
     *frameDelay = *(undefined2 *)(frameData + 3);
     frameFormatType = frameData[5];
   }
   existingPaletteBuffer = *(void **)(decoderState + 0x10);
   if (frameFormatType == 0) {
     if (existingPaletteBuffer != (void *)0x0) {
       free(existingPaletteBuffer);
     }
     paletteEntryCounter = 0x100;
     if ((byte)frameData[6] != 0) {
       paletteEntryCounter = (uint)(byte)frameData[6];
     }
     paletteEntryCount = (ulong)paletteEntryCounter;
     paletteIndex = paletteEntryCounter << 1;
     if (0xff < paletteIndex) {
       paletteIndex = 0x100;
     }
     *decoderState = (ushort)paletteEntryCounter;
     bitOffset = 0x40;
     if (0xf < paletteEntryCounter) {
       bitOffset = paletteIndex;
     }
     decoderState[1] = (ushort)bitOffset;
     newPaletteBuffer = (undefined8 *)malloc((ulong)(bitOffset * 6));
     *(undefined8 **)(decoderState + 0x10) = newPaletteBuffer;
     if (paletteEntryCounter == 0) {
       paletteEntryCount = 0;
     }
     else {
       paletteReadCursor = frameData + 7;
       if (paletteEntryCounter < 8) {
         alignedPaletteSize = 0;
       }
       else {
         if (paletteEntryCounter < 0x10) {
           currentPaletteCountUlong = 0;
         }
         else {
           alignedPaletteSize = paletteEntryCount & 0x1f0;
           currentPaletteCountUlong = alignedPaletteSize;
           paletteWriteCursor = newPaletteBuffer;
           paletteReadCursor = frameData + 7;
           do {
             paletteChunk1 = *(undefined8 *)(paletteReadCursor + 0x10);
             paletteChunk0 = *(undefined8 *)(paletteReadCursor + 0x28);
             paletteChunk4 = *(undefined8 *)(paletteReadCursor + 0x20);
             currentPaletteCountUlong = currentPaletteCountUlong - 0x10;
             paletteChunk3 = *(undefined8 *)(paletteReadCursor + 8);
             paletteChunk2 = *(undefined8 *)paletteReadCursor;
             paletteWriteCursor[3] = *(undefined8 *)(paletteReadCursor + 0x18);
             paletteWriteCursor[2] = paletteChunk1;
             paletteWriteCursor[5] = paletteChunk0;
             paletteWriteCursor[4] = paletteChunk4;
             paletteWriteCursor[1] = paletteChunk3;
             *paletteWriteCursor = paletteChunk2;
             paletteWriteCursor = paletteWriteCursor + 6;
             paletteReadCursor = paletteReadCursor + 0x30;
           } while (currentPaletteCountUlong != 0);
           if (alignedPaletteSize == paletteEntryCount) goto LAB_0025f184;
           currentPaletteCountUlong = alignedPaletteSize;
           if ((paletteEntryCounter >> 3 & 1) == 0) goto LAB_0025f148;
         }
         alignedPaletteSize = paletteEntryCount & 0x1f8;
         pixelBufferOffset = currentPaletteCountUlong - alignedPaletteSize;
         currentPaletteCountUlong = currentPaletteCountUlong * 3;
         do {
           paletteWriteCursor = (undefined8 *)((long)newPaletteBuffer + currentPaletteCountUlong);
           paletteReadCursor = frameData + 7 + (currentPaletteCountUlong & 0xfffffff8);
           currentPaletteCountUlong = currentPaletteCountUlong + 0x18;
           pixelBufferOffset = pixelBufferOffset + 8;
           paletteChunk0 = *(undefined8 *)(paletteReadCursor + 8);
           paletteChunk1 = *(undefined8 *)paletteReadCursor;
           paletteWriteCursor[2] = *(undefined8 *)(paletteReadCursor + 0x10);
           paletteWriteCursor[1] = paletteChunk0;
           *paletteWriteCursor = paletteChunk1;
         } while (pixelBufferOffset != 0);
         if (alignedPaletteSize == paletteEntryCount) goto LAB_0025f184;
       }
 LAB_0025f148:
       pixelBufferOffset = paletteEntryCount - alignedPaletteSize;
       alignedPaletteSize = alignedPaletteSize * 3;
       do {
         paletteCopyOffset = (int)alignedPaletteSize;
         currentPaletteCountUlong = alignedPaletteSize & 0xffffffff;
         paletteReadCursor = (char *)((long)newPaletteBuffer + alignedPaletteSize);
         pixelBufferOffset = pixelBufferOffset + -1;
         alignedPaletteSize = alignedPaletteSize + 3;
         paletteByte1 = (frameData + 7)[paletteCopyOffset + 1];
         paletteByte2 = (frameData + 7)[paletteCopyOffset + 2];
         *paletteReadCursor = (frameData + 7)[currentPaletteCountUlong];
         paletteReadCursor[1] = paletteByte1;
         paletteReadCursor[2] = paletteByte2;
       } while (pixelBufferOffset != 0);
     }
 LAB_0025f184:
     bitstreamOffset = (ulong)(paletteEntryCounter * 3 + 7);
     pixelBufferOffset = 0;
     paletteEntryCounter = 0;
     frameFormatType = (&gdivoom_image_bits_table)[paletteEntryCount];
     do {
     bitOffset = paletteEntryCounter & 7;
     paletteEntryCount = (ulong)(paletteEntryCounter >> 3);
     paletteIndex = bitOffset + frameFormatType;
     if (paletteIndex < 9) {
       paletteIndex = ((uint)(byte)frameData[paletteEntryCount + bitstreamOffset] << (ulong)(8 - paletteIndex & 0x1f) & 0xff) >>
                (ulong)((8 - paletteIndex) + bitOffset & 0x1f);
     }
     else {
       paletteIndex = (((uint)(byte)frameData[paletteEntryCount + bitstreamOffset + 1] << (ulong)(0x10 - paletteIndex & 0x1f) & 0xff)
                >> (ulong)(0x10 - paletteIndex & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                (uint)((byte)frameData[paletteEntryCount + bitstreamOffset] >> (ulong)bitOffset);
     }
     outputPixelPtr = (undefined1 *)(pixelBuffer + pixelBufferOffset);
       paletteEntryCounter = paletteEntryCounter + frameFormatType;
       pixelBufferOffset = pixelBufferOffset + 3;
     paletteEntryPtr = (undefined1 *)(*(long *)(decoderState + 0x10) + (ulong)(paletteIndex & 0xffff) * 3);
       *outputPixelPtr = *paletteEntryPtr;
       outputPixelPtr[1] = paletteEntryPtr[1];
       outputPixelPtr[2] = paletteEntryPtr[2];
     } while (pixelBufferOffset != 0x300);
     goto LAB_0025f24c;
   }
   if (existingPaletteBuffer == (void *)0x0) {
     errorCode = 0x158e;
     errorMessage = "err: %d!\n";
     goto LAB_0025edd0;
   }
   frameFormatType = frameData[6];
   paletteEntryCount = (ulong)frameFormatType;
   currentPaletteCount = *decoderState;
   currentPaletteCountUlong = (ulong)currentPaletteCount;
   if ((uint)decoderState[1] < (uint)currentPaletteCount + (uint)frameFormatType) {
     errorCode = 0x1594;
     errorMessage = "err: %d!\n";
     goto LAB_0025edd0;
   }
   if (frameFormatType == 0) {
     currentPaletteCountUlong = (ulong)(uint)currentPaletteCount;
   }
   else {
     if (frameFormatType < 8) {
 LAB_0025ee6c:
       alignedPaletteSize = 0;
     }
     else {
       bitstreamOffset = paletteEntryCount - 1;
       overflowCheck._8_8_ = 0;
       overflowCheck._0_8_ = bitstreamOffset;
       paletteEntryCounter = (uint)currentPaletteCount;
       hasOverflow = SUB168(overflowCheck * ZEXT816(3),8) != 0;
       if ((paletteEntryCounter + (ushort)bitstreamOffset >> 0x10 != 0) || (bitstreamOffset >> 0x10 != 0)) goto LAB_0025ee6c;
       pixelBufferOffset = bitstreamOffset * 3;
       paletteBufferPtr = (void *)((long)existingPaletteBuffer + currentPaletteCountUlong * 3);
       if (((long)paletteBufferPtr + 1U + pixelBufferOffset < (long)paletteBufferPtr + 1U) ||
          ((((hasOverflow || ((long)paletteBufferPtr + 2U + pixelBufferOffset < (long)paletteBufferPtr + 2U)) || (hasOverflow)) ||
           (((void *)((long)paletteBufferPtr + pixelBufferOffset) < paletteBufferPtr || (hasOverflow)))))) goto LAB_0025ee6c;
       paletteDataPtr = (ushort *)(frameData + 7);
       paletteWriteStart = (ushort *)((long)existingPaletteBuffer + currentPaletteCountUlong * 3);
       paletteWriteEnd = (ushort *)((long)existingPaletteBuffer + (paletteEntryCount + currentPaletteCountUlong) * 3);
       if ((decoderState < frameData + paletteEntryCount * 3 + 7 && paletteDataPtr < decoderState + 1) ||
          ((decoderState < paletteWriteEnd && paletteWriteStart < decoderState + 1 ||
           (paletteDataPtr < paletteWriteEnd && paletteWriteStart < frameData + paletteEntryCount * 3 + 7)))) goto LAB_0025ee6c;
       alignedPaletteSize = paletteEntryCount & 0xf8;
       bitstreamOffset = 0;
       currentPaletteCountUlong = (ulong)(paletteEntryCounter + (int)alignedPaletteSize);
       paletteCopyOffset = paletteEntryCounter + 7;
       do {
         paletteIndex = paletteEntryCounter + (int)bitstreamOffset;
         newPaletteCount = (short)paletteCopyOffset;
         bitstreamOffset = bitstreamOffset + 8;
         newPaletteBuffer = (undefined8 *)((long)existingPaletteBuffer + ((ulong)paletteIndex & 0xffff) + (ulong)(ushort)paletteIndex * 2)
         ;
         paletteCopyOffset = paletteCopyOffset + 8;
         paletteChunk0 = *(undefined8 *)(paletteDataPtr + 4);
         paletteChunk1 = *(undefined8 *)paletteDataPtr;
         newPaletteBuffer[2] = *(undefined8 *)(paletteDataPtr + 8);
         newPaletteBuffer[1] = paletteChunk0;
         *newPaletteBuffer = paletteChunk1;
         *decoderState = newPaletteCount + 1;
         paletteDataPtr = paletteDataPtr + 0xc;
       } while (alignedPaletteSize != bitstreamOffset);
       if (alignedPaletteSize == paletteEntryCount) goto LAB_0025ef14;
     }
     pixelBufferOffset = paletteEntryCount - alignedPaletteSize;
     paletteDataStart = frameData + alignedPaletteSize * 3 + 9;
     do {
       alignedPaletteSize = currentPaletteCountUlong & 0xffff;
       bitstreamOffset = currentPaletteCountUlong & 0xffff;
       paletteEntryCounter = (int)currentPaletteCountUlong + 1;
       currentPaletteCountUlong = (ulong)paletteEntryCounter;
       paletteReadCursor = (char *)((long)existingPaletteBuffer + alignedPaletteSize + bitstreamOffset * 2);
       pixelBufferOffset = pixelBufferOffset + -1;
       *paletteReadCursor = paletteDataStart[-2];
       paletteReadCursor[1] = paletteDataStart[-1];
       paletteByte1 = *paletteDataStart;
       *decoderState = (ushort)paletteEntryCounter;
       paletteReadCursor[2] = paletteByte1;
       paletteDataStart = paletteDataStart + 3;
     } while (pixelBufferOffset != 0);
   }
 LAB_0025ef14:
   pixelBufferOffset = 0;
   bitstreamOffset = paletteEntryCount * 3 + 7;
   paletteEntryCounter = 0;
   frameFormatType = (&gdivoom_image_bits_table)[currentPaletteCountUlong & 0xffff];
   do {
     bitOffset = paletteEntryCounter & 7;
     paletteEntryCount = (ulong)(paletteEntryCounter >> 3);
     paletteIndex = bitOffset + frameFormatType;
     if (paletteIndex < 9) {
       paletteIndex = ((uint)(byte)frameData[paletteEntryCount + bitstreamOffset] << (ulong)(8 - paletteIndex & 0x1f) & 0xff) >>
                (ulong)((8 - paletteIndex) + bitOffset & 0x1f);
     }
     else {
       paletteIndex = (((uint)(byte)frameData[paletteEntryCount + bitstreamOffset + 1] << (ulong)(0x10 - paletteIndex & 0x1f) & 0xff)
                >> (ulong)(0x10 - paletteIndex & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                (uint)((byte)frameData[paletteEntryCount + bitstreamOffset] >> (ulong)bitOffset);
     }
     outputPixelPtr = (undefined1 *)(pixelBuffer + pixelBufferOffset);
     paletteEntryCounter = paletteEntryCounter + frameFormatType;
     pixelBufferOffset = pixelBufferOffset + 3;
     paletteEntryPtr = (undefined1 *)(*(long *)(decoderState + 0x10) + (ulong)(paletteIndex & 0xffff) * 3);
     *outputPixelPtr = *paletteEntryPtr;
     outputPixelPtr[1] = paletteEntryPtr[1];
     outputPixelPtr[2] = paletteEntryPtr[2];
   } while (pixelBufferOffset != 0x300);
 LAB_0025f24c:
   if (bytesConsumed != (int *)0x0) {
     *bytesConsumed = (int)bitstreamOffset + (uint)frameFormatType * 0x20;
     return 1;
   }
   return 1;
 }
 
 
 undefined8
 divoom_image_decode_decode_one_128
           (ushort *decoderState,char *frameData,void *pixelBuffer,int *bytesConsumed,undefined2 *frameDelay)
 
 {
   char *paletteEntryPtr;
   undefined1 *outputPixelPtr;
   ushort *paletteWriteStart;
   ushort *paletteWriteEnd;
   undefined8 *paletteWriteCursor;
   uint bitOffset;
   char paletteByte;
   byte frameFormatType;
   ushort currentPaletteCount;
   ushort newPaletteSize;
   undefined1 overflowCheck [16];
   long paletteEntryOffset;
   short newPaletteCount;
   bool hasOverflow;
   void *paletteBufferPtr;
   char *errorMessageStr;
   char *paletteBuffer;
   undefined8 errorCode;
   uint paletteSizeUint;
   uint bitsPerIndex;
   ulong loopCounter;
   ulong paletteSizeUlong;
   ulong alignedPaletteSize;
   int paletteCopyOffset;
   ulong currentPaletteOffset;
   uint bitCursor;
   long remainingEntries;
   ushort *paletteDataPtr;
   char *paletteDataStart;
   char *paletteReadCursor;
   char *paletteSourceCursor;
   uint colorIndex;
   void *oldPaletteBuffer;
   undefined8 tempValue0;
   undefined8 tempValue1;
   undefined8 tempValue2;
   undefined8 tempValue3;
   undefined8 tempValue4;
   
   if (frameData == (char *)0x0) {
     errorCode = 0x112c;
     errorMessageStr = "err: %d!\n";
 LAB_0025cf7c:
     printf(errorMessageStr,errorCode);
     return 0;
   }
   if (*frameData != -0x56) {
     errorCode = 0x1131;
     errorMessageStr = "image flag err: %d!\n";
     goto LAB_0025cf7c;
   }
   frameFormatType = frameData[5];
   if (((frameFormatType & 0x7d) != 0x11) && ((frameFormatType & 0x7f) != 0x14)) {
     printf("image size err: %d: %d!\n",0x1137);
     return 0;
   }
   if (frameDelay != (undefined2 *)0x0) {
     *frameDelay = *(undefined2 *)(frameData + 3);
   }
   if ((frameFormatType & 0x7f) == 0x13) {
     oldPaletteBuffer = *(void **)(decoderState + 0x10);
     if (oldPaletteBuffer == (void *)0x0) {
       errorCode = 0x1158;
       errorMessageStr = "err: %d!\n";
       goto LAB_0025cf7c;
     }
     newPaletteSize = *(ushort *)(frameData + 6);
     paletteSizeUlong = (ulong)newPaletteSize;
     currentPaletteCount = *decoderState;
     remainingEntries = paletteSizeUlong + currentPaletteCount;
     paletteSizeUint = (uint)newPaletteSize;
     paletteBufferPtr = oldPaletteBuffer;
     if ((uint)decoderState[1] < (uint)remainingEntries) {
       paletteBufferPtr = malloc(remainingEntries * 6 + 0x600);
       if (paletteBufferPtr == (void *)0x0) {
         errorCode = 0x1163;
         errorMessageStr = "image size err: %d!\n";
         goto LAB_0025cf7c;
       }
       memcpy(paletteBufferPtr,oldPaletteBuffer,(ulong)currentPaletteCount * 3);
       decoderState[1] = currentPaletteCount + newPaletteSize + 0x100;
       free(oldPaletteBuffer);
       *(void **)(decoderState + 0x10) = paletteBufferPtr;
     }
     if (paletteSizeUint == 0) {
       currentPaletteOffset = (ulong)*decoderState;
     }
     else {
       newPaletteSize = *decoderState;
       currentPaletteOffset = (ulong)newPaletteSize;
       if (paletteSizeUint < 8) {
 LAB_0025d074:
         alignedPaletteSize = 0;
       }
       else {
         loopCounter = paletteSizeUlong - 1;
         overflowCheck._8_8_ = 0;
         overflowCheck._0_8_ = loopCounter;
         hasOverflow = SUB168(overflowCheck * ZEXT816(3),8) != 0;
         if (((uint)newPaletteSize + (uint)(ushort)loopCounter >> 0x10 != 0) || (loopCounter >> 0x10 != 0))
         goto LAB_0025d074;
         remainingEntries = loopCounter * 3;
         oldPaletteBuffer = (void *)((long)paletteBufferPtr + currentPaletteOffset * 3);
         if (((long)oldPaletteBuffer + 1U + remainingEntries < (long)oldPaletteBuffer + 1U) ||
            ((((hasOverflow || ((long)oldPaletteBuffer + 2U + remainingEntries < (long)oldPaletteBuffer + 2U)) || (hasOverflow)) ||
             (((void *)((long)oldPaletteBuffer + remainingEntries) < oldPaletteBuffer || (hasOverflow)))))) goto LAB_0025d074;
         paletteDataPtr = (ushort *)(frameData + 8);
         paletteWriteStart = (ushort *)((long)paletteBufferPtr + currentPaletteOffset * 3);
         paletteWriteEnd = (ushort *)((long)paletteBufferPtr + (currentPaletteOffset + paletteSizeUlong) * 3);
         if ((decoderState < frameData + paletteSizeUlong * 3 + 8 && paletteDataPtr < decoderState + 1) ||
            ((decoderState < paletteWriteEnd && paletteWriteStart < decoderState + 1 ||
             (paletteDataPtr < paletteWriteEnd && paletteWriteStart < frameData + paletteSizeUlong * 3 + 8)))) goto LAB_0025d074;
         alignedPaletteSize = paletteSizeUlong & 0xfff8;
         loopCounter = 0;
         currentPaletteOffset = (ulong)((uint)newPaletteSize + (int)alignedPaletteSize);
         paletteCopyOffset = newPaletteSize + 7;
         do {
           bitCursor = (uint)newPaletteSize + (int)loopCounter;
           newPaletteCount = (short)paletteCopyOffset;
           loopCounter = loopCounter + 8;
           paletteWriteCursor = (undefined8 *)
                    ((long)paletteBufferPtr + ((ulong)bitCursor & 0xffff) + (ulong)(ushort)bitCursor * 2);
           paletteCopyOffset = paletteCopyOffset + 8;
           tempValue2 = *(undefined8 *)(paletteDataPtr + 4);
           tempValue1 = *(undefined8 *)paletteDataPtr;
           paletteWriteCursor[2] = *(undefined8 *)(paletteDataPtr + 8);
           paletteWriteCursor[1] = tempValue2;
           *paletteWriteCursor = tempValue1;
           *decoderState = newPaletteCount + 1;
           paletteDataPtr = paletteDataPtr + 0xc;
         } while (alignedPaletteSize != loopCounter);
         if (alignedPaletteSize == paletteSizeUlong) goto LAB_0025d26c;
       }
       remainingEntries = paletteSizeUlong - alignedPaletteSize;
       paletteDataStart = frameData + alignedPaletteSize * 3 + 10;
       do {
         loopCounter = currentPaletteOffset & 0xffff;
         paletteSizeUlong = currentPaletteOffset & 0xffff;
         bitCursor = (int)currentPaletteOffset + 1;
         currentPaletteOffset = (ulong)bitCursor;
         paletteEntryPtr = (char *)((long)paletteBufferPtr + loopCounter + paletteSizeUlong * 2);
         remainingEntries = remainingEntries + -1;
         *paletteEntryPtr = paletteDataStart[-2];
         paletteEntryPtr[1] = paletteDataStart[-1];
         paletteByte = *paletteDataStart;
         *decoderState = (ushort)bitCursor;
         paletteEntryPtr[2] = paletteByte;
         paletteDataStart = paletteDataStart + 3;
       } while (remainingEntries != 0);
     }
 LAB_0025d26c:
     paletteSizeUint = paletteSizeUint * 3 + 8;
     remainingEntries = 0;
     bitCursor = 0;
     frameFormatType = (&gdivoom_image_bits_table)[currentPaletteOffset & 0xffff];
     bitsPerIndex = (uint)frameFormatType;
     newPaletteSize = (ushort)paletteSizeUint;
     do {
       bitOffset = bitCursor & 7;
       paletteSizeUlong = (ulong)(bitCursor >> 3);
       colorIndex = bitOffset + frameFormatType;
       if (colorIndex < 9) {
         colorIndex = ((uint)(byte)frameData[paletteSizeUlong + newPaletteSize] << (ulong)(8 - colorIndex & 0x1f) & 0xff) >>
                  (ulong)((8 - colorIndex) + bitOffset & 0x1f);
       }
       else {
         colorIndex = (((uint)(byte)frameData[paletteSizeUlong + newPaletteSize + 1] << (ulong)(0x10 - colorIndex & 0x1f) & 0xff)
                  >> (ulong)(0x10 - colorIndex & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                  (uint)((byte)frameData[paletteSizeUlong + newPaletteSize] >> (ulong)bitOffset);
       }
       outputPixelPtr = (undefined1 *)((long)pixelBuffer + remainingEntries);
       bitCursor = bitCursor + frameFormatType;
       paletteEntryOffset = (ulong)(colorIndex & 0xffff) * 3;
       remainingEntries = remainingEntries + 3;
       *outputPixelPtr = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset);
       outputPixelPtr[1] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 1);
       outputPixelPtr[2] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 2);
     } while ((int)remainingEntries != 0xc000);
     goto LAB_0025cfe4;
   }
   if ((frameFormatType & 0x7f) == 0x11) {
     if (*(void **)(decoderState + 0x10) != (void *)0x0) {
       free(*(void **)(decoderState + 0x10));
       decoderState[0x10] = 0;
       decoderState[0x11] = 0;
       decoderState[0x12] = 0;
       decoderState[0x13] = 0;
     }
     memcpy(pixelBuffer,frameData + 8,0xc000);
     bitsPerIndex = 0x18;
     paletteSizeUint = 8;
     goto LAB_0025cfe4;
   }
   newPaletteSize = *(ushort *)(frameData + 6);
   paletteBuffer = *(char **)(decoderState + 0x10);
   paletteSizeUint = (uint)newPaletteSize;
   *decoderState = newPaletteSize;
   if (newPaletteSize < 0x81) {
     paletteSizeUint = 0x80;
   }
   if (paletteBuffer == (char *)0x0) {
 LAB_0025d0f0:
     decoderState[1] = (ushort)paletteSizeUint;
     paletteBuffer = (char *)malloc((ulong)paletteSizeUint * 6);
     *(char **)(decoderState + 0x10) = paletteBuffer;
   }
   else if (decoderState[1] != paletteSizeUint) {
     free(paletteBuffer);
     newPaletteSize = *decoderState;
     goto LAB_0025d0f0;
   }
   paletteSizeUint = (uint)newPaletteSize;
   if (paletteSizeUint == 0) {
     paletteSizeUlong = 0;
   }
   else {
     paletteReadCursor = frameData + 8;
     paletteSizeUlong = (ulong)paletteSizeUint;
     if ((paletteSizeUint < 8) || ((paletteBuffer < frameData + paletteSizeUlong * 3 + 8 && (paletteReadCursor < paletteBuffer + paletteSizeUlong * 3)))) {
       currentPaletteOffset = 0;
     }
     else {
       if (paletteSizeUint < 0x10) {
         loopCounter = 0;
       }
       else {
         currentPaletteOffset = paletteSizeUlong & 0xfff0;
         loopCounter = currentPaletteOffset;
         paletteWriteCursor = (undefined8 *)paletteBuffer;
         paletteSourceCursor = paletteReadCursor;
         do {
           tempValue2 = *(undefined8 *)(paletteSourceCursor + 0x10);
           tempValue1 = *(undefined8 *)(paletteSourceCursor + 0x28);
           tempValue0 = *(undefined8 *)(paletteSourceCursor + 0x20);
           loopCounter = loopCounter - 0x10;
           tempValue4 = *(undefined8 *)(paletteSourceCursor + 8);
           tempValue3 = *(undefined8 *)paletteSourceCursor;
           *(undefined8 *)(paletteWriteCursor + 0x18) = *(undefined8 *)(paletteSourceCursor + 0x18);
           *(undefined8 *)(paletteWriteCursor + 0x10) = tempValue2;
           *(undefined8 *)(paletteWriteCursor + 0x28) = tempValue1;
           *(undefined8 *)(paletteWriteCursor + 0x20) = tempValue0;
           *(undefined8 *)(paletteWriteCursor + 8) = tempValue4;
           *(undefined8 *)paletteWriteCursor = tempValue3;
           paletteWriteCursor = (undefined8 *)((char *)paletteWriteCursor + 0x30);
           paletteSourceCursor = paletteSourceCursor + 0x30;
         } while (loopCounter != 0);
         if (currentPaletteOffset == paletteSizeUlong) goto LAB_0025d194;
         loopCounter = currentPaletteOffset;
         if ((newPaletteSize >> 3 & 1) == 0) goto LAB_0025d13c;
       }
       currentPaletteOffset = paletteSizeUlong & 0xfff8;
       remainingEntries = loopCounter - currentPaletteOffset;
       loopCounter = loopCounter * 3;
       do {
         paletteWriteCursor = (undefined8 *)(paletteBuffer + loopCounter);
         paletteSourceCursor = paletteReadCursor + (loopCounter & 0xfffffff8);
         loopCounter = loopCounter + 0x18;
         remainingEntries = remainingEntries + 8;
         tempValue1 = *(undefined8 *)(paletteSourceCursor + 8);
         tempValue0 = *(undefined8 *)paletteSourceCursor;
         *(undefined8 *)(paletteWriteCursor + 0x10) = *(undefined8 *)(paletteSourceCursor + 0x10);
         *(undefined8 *)(paletteWriteCursor + 8) = tempValue1;
         *(undefined8 *)paletteWriteCursor = tempValue0;
       } while (remainingEntries != 0);
       if (currentPaletteOffset == paletteSizeUlong) goto LAB_0025d194;
     }
 LAB_0025d13c:
     remainingEntries = paletteSizeUlong - currentPaletteOffset;
     currentPaletteOffset = currentPaletteOffset * 3;
     do {
       paletteWriteCursor = (undefined8 *)(paletteBuffer + currentPaletteOffset);
       paletteCopyOffset = (int)currentPaletteOffset;
       remainingEntries = remainingEntries + -1;
       *(char *)paletteWriteCursor = paletteReadCursor[currentPaletteOffset & 0xffffffff];
       currentPaletteOffset = currentPaletteOffset + 3;
       ((char *)paletteWriteCursor)[1] = paletteReadCursor[paletteCopyOffset + 1];
       ((char *)paletteWriteCursor)[2] = paletteReadCursor[paletteCopyOffset + 2];
     } while (remainingEntries != 0);
   }
 LAB_0025d194:
   paletteSizeUint = paletteSizeUint * 3 + 8;
   remainingEntries = 0;
   bitCursor = 0;
   frameFormatType = (&gdivoom_image_bits_table)[paletteSizeUlong];
   bitsPerIndex = (uint)frameFormatType;
   newPaletteSize = (ushort)paletteSizeUint;
   do {
     bitOffset = bitCursor & 7;
     paletteSizeUlong = (ulong)(bitCursor >> 3);
     colorIndex = bitOffset + frameFormatType;
     if (colorIndex < 9) {
       colorIndex = ((uint)(byte)frameData[paletteSizeUlong + newPaletteSize] << (ulong)(8 - colorIndex & 0x1f) & 0xff) >>
                (ulong)((8 - colorIndex) + bitOffset & 0x1f);
     }
     else {
       colorIndex = (((uint)(byte)frameData[paletteSizeUlong + newPaletteSize + 1] << (ulong)(0x10 - colorIndex & 0x1f) & 0xff)
                >> (ulong)(0x10 - colorIndex & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                (uint)((byte)frameData[paletteSizeUlong + newPaletteSize] >> (ulong)bitOffset);
     }
     outputPixelPtr = (undefined1 *)((long)pixelBuffer + remainingEntries);
     bitCursor = bitCursor + frameFormatType;
     paletteEntryOffset = (ulong)(colorIndex & 0xffff) * 3;
     remainingEntries = remainingEntries + 3;
     *outputPixelPtr = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset);
     outputPixelPtr[1] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 1);
     outputPixelPtr[2] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 2);
   } while ((int)remainingEntries != 0xc000);
 LAB_0025cfe4:
   if (bytesConsumed == (int *)0x0) {
     return 1;
   }
   *bytesConsumed = bitsPerIndex * 0x800 + (paletteSizeUint & 0xffff);
   return 1;
 }
 
 
 undefined8
 divoom_image_decode_decode_one_64
           (ushort *decoderState,char *frameData,void *pixelBuffer,int *bytesConsumed,undefined2 *frameDelay)
 
 {
   char *paletteDataStart;
   ushort *paletteWriteStart;
   ushort *paletteWriteEnd;
   undefined8 *paletteWriteCursor;
   undefined1 *outputPixelPtr;
   uint bitOffset;
   char paletteByte1;
   byte frameFormatType;
   ushort currentPaletteCount;
   ushort newPaletteSize;
   undefined1 overflowCheck [16];
   long paletteEntryOffset;
   short newPaletteCount;
   bool hasOverflow;
   undefined8 errorCode;
   void *paletteBufferPtr;
   char *errorMessage;
   uint bitstreamOffset;
   uint bitsPerIndexUint;
   ulong paletteCopySize;
   ulong paletteEntryCount;
   ulong alignedPaletteSize;
   int paletteCopyOffset;
   ulong currentPaletteOffset;
   uint bitCursor;
   ushort *paletteDataPtr;
   char *paletteReadCursor;
   char *existingPaletteBuffer;
   uint paletteIndex;
   void *existingPaletteBufferVoid;
   undefined8 paletteChunk0;
   undefined8 paletteChunk1;
   undefined8 paletteChunk2;
   undefined8 paletteChunk3;
   undefined8 paletteChunk4;
   ulong newPaletteSizeUlong;
   ulong totalPaletteSize;
   uint newPaletteSizeUint;
   uint currentPaletteCountUint;
   uint paletteAllocSize;
   uint paletteEntryCounter;
   ulong byteOffset;
   uint totalBits;
   long pixelBufferOffset;
   byte bitsPerIndex;
   ushort bitstreamOffsetUshort;
   void *paletteWritePtr;
   ulong paletteCopyBytes;
   
   if (frameData == (char *)0x0) {
     errorCode = 0x108d;
     errorMessage = "err: %d!\n";
 LAB_0025c924:
     printf(errorMessage,errorCode);
 LAB_0025c928:
     errorCode = 0;
   }
   else {
     if (*frameData != -0x56) {
       errorCode = 0x1092;
       errorMessage = "image flag err: %d!\n";
       goto LAB_0025c924;
     }
     frameFormatType = frameData[5];
     if ((frameFormatType & 0x7f) - 0x11 < 0xfffffffa) {
       printf("image size err: %d: %d!\n",0x1099);
       goto LAB_0025c928;
     }
     if (frameDelay != (undefined2 *)0x0) {
       *frameDelay = *(undefined2 *)(frameData + 3);
     }
     switch((uint)frameFormatType) {
     case 0xb:
     case 0xe:
 switchD_0025c984_caseD_8b:
       if (*(void **)(decoderState + 0x10) != (void *)0x0) {
         free(*(void **)(decoderState + 0x10));
         decoderState[0x10] = 0;
         decoderState[0x11] = 0;
         decoderState[0x12] = 0;
         decoderState[0x13] = 0;
       }
       memcpy(pixelBuffer,frameData + 8,0x3000);
       bitsPerIndexUint = 0x18;
       bitstreamOffset = 8;
       break;
     case 0xc:
     case 0xf:
 switchD_0025c984_caseD_8c:
       currentPaletteCount = *(ushort *)(frameData + 6);
       existingPaletteBufferVoid = *(void **)(decoderState + 0x10);
       existingPaletteBuffer = (char *)existingPaletteBufferVoid;
       paletteAllocSize = (uint)currentPaletteCount;
       *decoderState = currentPaletteCount;
       if (currentPaletteCount < 0x81) {
         paletteAllocSize = 0x80;
       }
       if (existingPaletteBufferVoid == (void *)0x0) {
 LAB_0025caec:
         decoderState[1] = (ushort)paletteAllocSize;
         existingPaletteBufferVoid = malloc((ulong)paletteAllocSize * 6);
         existingPaletteBuffer = (char *)existingPaletteBufferVoid;
         *(void **)(decoderState + 0x10) = existingPaletteBufferVoid;
       }
       else if (decoderState[1] != paletteAllocSize) {
         free(existingPaletteBufferVoid);
         currentPaletteCount = *decoderState;
         goto LAB_0025caec;
       }
       paletteEntryCounter = (uint)currentPaletteCount;
       if (paletteEntryCounter == 0) {
         currentPaletteOffset = 0;
       }
       else {
         paletteDataStart = frameData + 8;
         paletteEntryCount = (ulong)paletteEntryCounter;
         if ((paletteEntryCounter < 8) ||
            ((existingPaletteBuffer < frameData + paletteEntryCount * 3 + 8 && (paletteDataStart < existingPaletteBuffer + paletteEntryCount * 3)))) {
           alignedPaletteSize = 0;
         }
         else {
           if (paletteEntryCounter < 0x10) {
             paletteCopySize = 0;
           }
           else {
             alignedPaletteSize = paletteEntryCount & 0xfff0;
             paletteCopySize = alignedPaletteSize;
             paletteWriteCursor = (undefined8 *)existingPaletteBuffer;
             paletteReadCursor = paletteDataStart;
             do {
               paletteChunk2 = *(undefined8 *)(paletteReadCursor + 0x10);
               paletteChunk1 = *(undefined8 *)(paletteReadCursor + 0x28);
               paletteChunk0 = *(undefined8 *)(paletteReadCursor + 0x20);
               paletteCopySize = paletteCopySize - 0x10;
               paletteChunk4 = *(undefined8 *)(paletteReadCursor + 8);
               paletteChunk3 = *(undefined8 *)paletteReadCursor;
               *(undefined8 *)(paletteWriteCursor + 0x18) = *(undefined8 *)(paletteReadCursor + 0x18);
               *(undefined8 *)(paletteWriteCursor + 0x10) = paletteChunk2;
               *(undefined8 *)(paletteWriteCursor + 0x28) = paletteChunk1;
               *(undefined8 *)(paletteWriteCursor + 0x20) = paletteChunk0;
               *(undefined8 *)(paletteWriteCursor + 8) = paletteChunk4;
               *(undefined8 *)paletteWriteCursor = paletteChunk3;
               paletteWriteCursor = paletteWriteCursor + 0x30;
               paletteReadCursor = paletteReadCursor + 0x30;
             } while (paletteCopySize != 0);
             if (alignedPaletteSize == paletteEntryCount) goto LAB_0025cd98;
             paletteCopySize = alignedPaletteSize;
             if ((currentPaletteCount >> 3 & 1) == 0) goto LAB_0025cb38;
           }
           alignedPaletteSize = paletteEntryCount & 0xfff8;
           paletteCopyBytes = paletteCopySize - alignedPaletteSize;
           paletteCopySize = paletteCopySize * 3;
           do {
             paletteWriteCursor = (undefined8 *)(existingPaletteBuffer + paletteCopySize);
             paletteReadCursor = paletteDataStart + (paletteCopySize & 0xfffffff8);
             paletteCopySize = paletteCopySize + 0x18;
             paletteCopyBytes = paletteCopyBytes + 8;
             paletteChunk1 = *(undefined8 *)(paletteReadCursor + 8);
             paletteChunk0 = *(undefined8 *)paletteReadCursor;
             *(undefined8 *)(paletteWriteCursor + 0x10) = *(undefined8 *)(paletteReadCursor + 0x10);
             *(undefined8 *)(paletteWriteCursor + 8) = paletteChunk1;
             *(undefined8 *)paletteWriteCursor = paletteChunk0;
           } while (paletteCopyBytes != 0);
           if (alignedPaletteSize == paletteEntryCount) goto LAB_0025cd98;
         }
 LAB_0025cb38:
         paletteCopyBytes = paletteEntryCount - alignedPaletteSize;
         alignedPaletteSize = alignedPaletteSize * 3;
         do {
           paletteWriteCursor = (undefined8 *)(existingPaletteBuffer + alignedPaletteSize);
           paletteCopyOffset = (int)alignedPaletteSize;
           paletteCopyBytes = paletteCopyBytes + -1;
           *((char *)paletteWriteCursor) = paletteDataStart[alignedPaletteSize & 0xffffffff];
           alignedPaletteSize = alignedPaletteSize + 3;
           ((char *)paletteWriteCursor)[1] = paletteDataStart[paletteCopyOffset + 1];
           ((char *)paletteWriteCursor)[2] = paletteDataStart[paletteCopyOffset + 2];
         } while (paletteCopyBytes != 0);
       }
 LAB_0025cd98:
       bitstreamOffset = paletteEntryCounter * 3 + 8;
       pixelBufferOffset = 0;
       bitCursor = 0;
       bitsPerIndex = (&gdivoom_image_bits_table)[currentPaletteOffset];
       bitsPerIndexUint = (uint)bitsPerIndex;
       bitstreamOffsetUshort = (ushort)bitstreamOffset;
       do {
         bitOffset = bitCursor & 7;
         byteOffset = (ulong)(bitCursor >> 3);
         totalBits = bitOffset + bitsPerIndex;
         if (totalBits < 9) {
           paletteIndex = ((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort] << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                    (ulong)((8 - totalBits) + bitOffset & 0x1f);
         }
         else {
           paletteIndex = (((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort + 1] << (ulong)(0x10 - totalBits & 0x1f) &
                     0xff) >> (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                    (uint)((byte)frameData[byteOffset + bitstreamOffsetUshort] >> (ulong)bitOffset);
         }
         outputPixelPtr = (undefined1 *)((long)pixelBuffer + pixelBufferOffset);
         bitCursor = bitCursor + bitsPerIndex;
         paletteEntryOffset = (ulong)(paletteIndex & 0xffff) * 3;
         pixelBufferOffset = pixelBufferOffset + 3;
         *outputPixelPtr = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset);
         outputPixelPtr[1] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 1);
         outputPixelPtr[2] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 2);
       } while ((int)pixelBufferOffset != 0x3000);
       break;
     case 0xd:
     case 0x10:
 switchD_0025c984_caseD_8d:
       existingPaletteBufferVoid = *(void **)(decoderState + 0x10);
       if (existingPaletteBufferVoid == (void *)0x0) {
         errorCode = 0x10ba;
         errorMessage = "err: %d!\n";
         goto LAB_0025c924;
       }
       newPaletteSize = *(ushort *)(frameData + 6);
       newPaletteSizeUlong = (ulong)newPaletteSize;
       currentPaletteCount = *decoderState;
       totalPaletteSize = newPaletteSizeUlong + currentPaletteCount;
       newPaletteSizeUint = (uint)newPaletteSize;
       paletteBufferPtr = existingPaletteBufferVoid;
       if ((uint)decoderState[1] < (uint)totalPaletteSize) {
         paletteBufferPtr = malloc(totalPaletteSize * 6 + 0x600);
         if (paletteBufferPtr == (void *)0x0) {
           errorCode = 0x10c5;
           errorMessage = "image size err: %d!\n";
           goto LAB_0025c924;
         }
         memcpy(paletteBufferPtr,existingPaletteBufferVoid,(ulong)currentPaletteCount * 3);
         decoderState[1] = currentPaletteCount + newPaletteSize + 0x100;
         free(existingPaletteBufferVoid);
         *(void **)(decoderState + 0x10) = paletteBufferPtr;
       }
       if (newPaletteSizeUint == 0) {
         currentPaletteOffset = (ulong)*decoderState;
       }
       else {
         currentPaletteCount = *decoderState;
         currentPaletteOffset = (ulong)currentPaletteCount;
         if (newPaletteSizeUint < 8) {
 LAB_0025ca58:
           alignedPaletteSize = 0;
         }
         else {
           paletteCopySize = newPaletteSizeUlong - 1;
           overflowCheck._8_8_ = 0;
           overflowCheck._0_8_ = paletteCopySize;
           currentPaletteCountUint = (uint)currentPaletteCount;
           hasOverflow = SUB168(overflowCheck * ZEXT816(3),8) != 0;
           if (((uint)currentPaletteCount + (uint)(ushort)paletteCopySize >> 0x10 != 0) || (paletteCopySize >> 0x10 != 0))
           goto LAB_0025ca58;
           paletteCopyBytes = paletteCopySize * 3;
           paletteWritePtr = (void *)((long)paletteBufferPtr + currentPaletteOffset * 3);
           if (((long)paletteWritePtr + 1U + paletteCopyBytes < (long)paletteWritePtr + 1U) ||
              ((((hasOverflow || ((long)paletteWritePtr + 2U + paletteCopyBytes < (long)paletteWritePtr + 2U)) || (hasOverflow)) ||
               (((void *)((long)paletteWritePtr + paletteCopyBytes) < paletteWritePtr || (hasOverflow)))))) goto LAB_0025ca58;
           paletteDataPtr = (ushort *)(frameData + 8);
           paletteWriteStart = (ushort *)((long)paletteBufferPtr + currentPaletteOffset * 3);
           paletteWriteEnd = (ushort *)((long)paletteBufferPtr + (currentPaletteOffset + newPaletteSizeUlong) * 3);
           if ((decoderState < frameData + newPaletteSizeUlong * 3 + 8 && paletteDataPtr < decoderState + 1) ||
              ((decoderState < paletteWriteEnd && paletteWriteStart < decoderState + 1 ||
               (paletteDataPtr < paletteWriteEnd && paletteWriteStart < frameData + newPaletteSizeUlong * 3 + 8)))) goto LAB_0025ca58;
           alignedPaletteSize = newPaletteSizeUlong & 0xfff8;
           paletteCopySize = 0;
           currentPaletteOffset = (ulong)(currentPaletteCountUint + (int)alignedPaletteSize);
           paletteCopyOffset = currentPaletteCountUint + 7;
           do {
             paletteIndex = currentPaletteCountUint + (int)paletteCopySize;
             newPaletteCount = (short)paletteCopyOffset;
             paletteCopySize = paletteCopySize + 8;
             paletteWriteCursor = (undefined8 *)
                      ((long)paletteBufferPtr + ((ulong)paletteIndex & 0xffff) + (ulong)(ushort)paletteIndex * 2);
             paletteCopyOffset = paletteCopyOffset + 8;
             paletteChunk0 = *(undefined8 *)(paletteDataPtr + 4);
             paletteChunk1 = *(undefined8 *)paletteDataPtr;
             paletteWriteCursor[2] = *(undefined8 *)(paletteDataPtr + 8);
             paletteWriteCursor[1] = paletteChunk0;
             *paletteWriteCursor = paletteChunk1;
             *decoderState = newPaletteCount + 1;
             paletteDataPtr = paletteDataPtr + 0xc;
           } while (alignedPaletteSize != paletteCopySize);
           if (alignedPaletteSize == newPaletteSizeUlong) goto LAB_0025cb78;
         }
         paletteCopyBytes = newPaletteSizeUlong - alignedPaletteSize;
         paletteDataStart = frameData + alignedPaletteSize * 3 + 10;
         do {
           paletteCopySize = currentPaletteOffset & 0xffff;
           newPaletteSizeUlong = currentPaletteOffset & 0xffff;
           paletteIndex = (int)currentPaletteOffset + 1;
           currentPaletteOffset = (ulong)paletteIndex;
           paletteReadCursor = (char *)((long)paletteBufferPtr + paletteCopySize + newPaletteSizeUlong * 2);
           paletteCopyBytes = paletteCopyBytes + -1;
           *paletteReadCursor = paletteDataStart[-2];
           paletteReadCursor[1] = paletteDataStart[-1];
           paletteByte1 = *paletteDataStart;
           *decoderState = (ushort)paletteIndex;
           paletteReadCursor[2] = paletteByte1;
           paletteDataStart = paletteDataStart + 3;
         } while (paletteCopyBytes != 0);
       }
 LAB_0025cb78:
       bitstreamOffset = newPaletteSizeUint * 3 + 8;
       pixelBufferOffset = 0;
       bitCursor = 0;
       bitsPerIndex = (&gdivoom_image_bits_table)[currentPaletteOffset & 0xffff];
       bitsPerIndexUint = (uint)bitsPerIndex;
       bitstreamOffsetUshort = (ushort)bitstreamOffset;
       do {
         bitOffset = bitCursor & 7;
         byteOffset = (ulong)(bitCursor >> 3);
         totalBits = bitOffset + bitsPerIndex;
         if (totalBits < 9) {
           paletteIndex = ((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort] << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                    (ulong)((8 - totalBits) + bitOffset & 0x1f);
         }
         else {
           paletteIndex = (((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort + 1] << (ulong)(0x10 - totalBits & 0x1f) &
                     0xff) >> (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                    (uint)((byte)frameData[byteOffset + bitstreamOffsetUshort] >> (ulong)bitOffset);
         }
         outputPixelPtr = (undefined1 *)((long)pixelBuffer + pixelBufferOffset);
         bitCursor = bitCursor + bitsPerIndex;
         paletteEntryOffset = (ulong)(paletteIndex & 0xffff) * 3;
         pixelBufferOffset = pixelBufferOffset + 3;
         *outputPixelPtr = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset);
         outputPixelPtr[1] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 1);
         outputPixelPtr[2] = *(undefined1 *)(*(long *)(decoderState + 0x10) + paletteEntryOffset + 2);
       } while ((int)pixelBufferOffset != 0x3000);
       break;
     default:
       switch(frameFormatType) {
       case 0x8b:
       case 0x8e:
         goto switchD_0025c984_caseD_8b;
       default:
         goto switchD_0025c984_caseD_8c;
       case 0x8d:
       case 0x90:
         goto switchD_0025c984_caseD_8d;
       }
     }
     if (bytesConsumed == (int *)0x0) {
       errorCode = 1;
     }
     else {
       errorCode = 1;
       *bytesConsumed = bitsPerIndexUint * 0x200 + (bitstreamOffset & 0xffff);
     }
   }
   return errorCode;
 }
 
 
 undefined8
 divoom_image_decode_decode_one_big
           (ushort *decoderState,char *frameData,void *pixelBuffer,int *bytesConsumed,undefined2 *frameDelay)
 
 {
   ushort currentPaletteCount;
   char *paletteReadCursor;
   undefined1 *outputPixelPtr;
   undefined1 *paletteEntryPtr;
   ushort *paletteWriteStart;
   ushort *paletteWriteEnd;
   undefined8 *paletteWriteCursor;
   uint bitOffset;
   char paletteByte1;
   byte frameFormatType;
   ushort newPaletteSize;
   undefined1 overflowCheck [16];
   short newPaletteCount;
   bool hasOverflow;
   void *paletteBufferPtr;
   char *errorMessage;
   undefined8 errorCode;
   uint bitstreamOffset;
   uint bitsPerIndexUint;
   ulong paletteCopySize;
   ulong paletteEntryCount;
   ulong alignedPaletteSize;
   int paletteCopyOffset;
   ulong currentPaletteOffset;
   uint bitCursor;
   ushort *paletteDataPtr;
   char *paletteDataStart;
   char *existingPaletteBuffer;
   uint paletteIndex;
   void *existingPaletteBufferVoid;
   uint newPaletteSizeUint;
   undefined8 paletteChunk0;
   undefined8 paletteChunk1;
   undefined8 paletteChunk2;
   undefined8 paletteChunk3;
   undefined8 paletteChunk4;
   ulong newPaletteSizeUlong;
   ulong totalPaletteSize;
   uint paletteAllocSize;
   uint paletteEntryCounter;
   uint currentPaletteCountUint;
   ulong byteOffset;
   uint totalBits;
   long pixelBufferOffset;
   byte bitsPerIndex;
   ushort bitstreamOffsetUshort;
   void *paletteWritePtr;
   ulong paletteCopyBytes;
   
   if (frameData == (char *)0x0) {
     errorCode = 0x14db;
     errorMessage = "err: %d!\n";
 LAB_0025e724:
     printf(errorMessage,errorCode);
     return 0;
   }
   if (*frameData != -0x56) {
     errorCode = 0x14e0;
     errorMessage = "image flag err: %d!\n";
     goto LAB_0025e724;
   }
   frameFormatType = frameData[5];
   if (((frameFormatType & 0x7e) != 2) && ((frameFormatType & 0x7f) != 4)) {
     printf("image size err: %d: %d!\n",0x14e6);
     return 0;
   }
   if (frameDelay != (undefined2 *)0x0) {
     *frameDelay = *(undefined2 *)(frameData + 3);
   }
   if ((frameFormatType & 0x7f) == 4) {
     existingPaletteBufferVoid = *(void **)(decoderState + 0x10);
     if (existingPaletteBufferVoid == (void *)0x0) {
       errorCode = 0x14fe;
       errorMessage = "err: %d!\n";
       goto LAB_0025e724;
     }
     newPaletteSize = *(ushort *)(frameData + 6);
     newPaletteSizeUlong = (ulong)newPaletteSize;
     currentPaletteCount = *decoderState;
     totalPaletteSize = newPaletteSizeUlong + currentPaletteCount;
     newPaletteSizeUint = (uint)newPaletteSize;
     paletteBufferPtr = existingPaletteBufferVoid;
     if ((uint)decoderState[1] < (uint)totalPaletteSize) {
       paletteBufferPtr = malloc(totalPaletteSize * 6 + 0x600);
       if (paletteBufferPtr == (void *)0x0) {
         errorCode = 0x1509;
         errorMessage = "image size err: %d!\n";
         goto LAB_0025e724;
       }
       memcpy(paletteBufferPtr,existingPaletteBufferVoid,(ulong)currentPaletteCount * 3);
       decoderState[1] = currentPaletteCount + newPaletteSize + 0x100;
       free(existingPaletteBufferVoid);
       *(void **)(decoderState + 0x10) = paletteBufferPtr;
     }
     if (newPaletteSizeUint == 0) {
       currentPaletteOffset = (ulong)*decoderState;
     }
     else {
       currentPaletteCount = *decoderState;
       currentPaletteOffset = (ulong)currentPaletteCount;
       if (newPaletteSizeUint < 8) {
 LAB_0025e81c:
         alignedPaletteSize = 0;
       }
       else {
         paletteCopySize = newPaletteSizeUlong - 1;
         overflowCheck._8_8_ = 0;
         overflowCheck._0_8_ = paletteCopySize;
         currentPaletteCountUint = (uint)currentPaletteCount;
         hasOverflow = SUB168(overflowCheck * ZEXT816(3),8) != 0;
         if (((uint)currentPaletteCount + (uint)(ushort)paletteCopySize >> 0x10 != 0) || (paletteCopySize >> 0x10 != 0))
         goto LAB_0025e81c;
         paletteCopyBytes = paletteCopySize * 3;
         paletteWritePtr = (void *)((long)paletteBufferPtr + currentPaletteOffset * 3);
         if (((long)paletteWritePtr + 1U + paletteCopyBytes < (long)paletteWritePtr + 1U) ||
            ((((hasOverflow || ((long)paletteWritePtr + 2U + paletteCopyBytes < (long)paletteWritePtr + 2U)) || (hasOverflow)) ||
             (((void *)((long)paletteWritePtr + paletteCopyBytes) < paletteWritePtr || (hasOverflow)))))) goto LAB_0025e81c;
         paletteDataPtr = (ushort *)(frameData + 8);
         paletteWriteStart = (ushort *)((long)paletteBufferPtr + currentPaletteOffset * 3);
         paletteWriteEnd = (ushort *)((long)paletteBufferPtr + (currentPaletteOffset + newPaletteSizeUlong) * 3);
         if ((decoderState < frameData + newPaletteSizeUlong * 3 + 8 && paletteDataPtr < decoderState + 1) ||
            ((decoderState < paletteWriteEnd && paletteWriteStart < decoderState + 1 ||
             (paletteDataPtr < paletteWriteEnd && paletteWriteStart < frameData + newPaletteSizeUlong * 3 + 8)))) goto LAB_0025e81c;
         alignedPaletteSize = newPaletteSizeUlong & 0xfff8;
         paletteCopySize = 0;
         currentPaletteOffset = (ulong)(currentPaletteCountUint + (int)alignedPaletteSize);
         paletteCopyOffset = currentPaletteCountUint + 7;
         do {
           paletteIndex = currentPaletteCountUint + (int)paletteCopySize;
           newPaletteCount = (short)paletteCopyOffset;
           paletteCopySize = paletteCopySize + 8;
           paletteWriteCursor = (undefined8 *)
                    ((long)paletteBufferPtr + ((ulong)paletteIndex & 0xffff) + (ulong)(ushort)paletteIndex * 2);
           paletteCopyOffset = paletteCopyOffset + 8;
           paletteChunk0 = *(undefined8 *)(paletteDataPtr + 4);
           paletteChunk1 = *(undefined8 *)paletteDataPtr;
           paletteWriteCursor[2] = *(undefined8 *)(paletteDataPtr + 8);
           paletteWriteCursor[1] = paletteChunk0;
           *paletteWriteCursor = paletteChunk1;
           *decoderState = newPaletteCount + 1;
           paletteDataPtr = paletteDataPtr + 0xc;
         } while (alignedPaletteSize != paletteCopySize);
         if (alignedPaletteSize == newPaletteSizeUlong) goto LAB_0025ea10;
       }
       paletteCopyBytes = newPaletteSizeUlong - alignedPaletteSize;
       paletteDataStart = frameData + alignedPaletteSize * 3 + 10;
       do {
         paletteCopySize = currentPaletteOffset & 0xffff;
         newPaletteSizeUlong = currentPaletteOffset & 0xffff;
         paletteIndex = (int)currentPaletteOffset + 1;
         currentPaletteOffset = (ulong)paletteIndex;
         paletteReadCursor = (char *)((long)paletteBufferPtr + paletteCopySize + newPaletteSizeUlong * 2);
         paletteCopyBytes = paletteCopyBytes + -1;
         *paletteReadCursor = paletteDataStart[-2];
         paletteReadCursor[1] = paletteDataStart[-1];
         paletteByte1 = *paletteDataStart;
         *decoderState = (ushort)paletteIndex;
         paletteReadCursor[2] = paletteByte1;
         paletteDataStart = paletteDataStart + 3;
       } while (paletteCopyBytes != 0);
     }
 LAB_0025ea10:
     bitstreamOffset = newPaletteSizeUint * 3 + 8;
     pixelBufferOffset = 0;
     bitCursor = 0;
     bitsPerIndex = (&gdivoom_image_bits_table)[currentPaletteOffset & 0xffff];
     bitsPerIndexUint = (uint)bitsPerIndex;
     bitstreamOffsetUshort = (ushort)bitstreamOffset;
     do {
       bitOffset = bitCursor & 7;
       byteOffset = (ulong)(bitCursor >> 3);
       totalBits = bitOffset + bitsPerIndex;
       if (totalBits < 9) {
         paletteIndex = ((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort] << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                  (ulong)((8 - totalBits) + bitOffset & 0x1f);
       }
       else {
         paletteIndex = (((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort + 1] << (ulong)(0x10 - totalBits & 0x1f) & 0xff)
                  >> (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                  (uint)((byte)frameData[byteOffset + bitstreamOffsetUshort] >> (ulong)bitOffset);
       }
       outputPixelPtr = (undefined1 *)((long)pixelBuffer + pixelBufferOffset);
       bitCursor = bitCursor + bitsPerIndex;
       pixelBufferOffset = pixelBufferOffset + 3;
       paletteEntryPtr = (undefined1 *)(*(long *)(decoderState + 0x10) + (ulong)(paletteIndex & 0xffff) * 3);
       *outputPixelPtr = *paletteEntryPtr;
       outputPixelPtr[1] = paletteEntryPtr[1];
       outputPixelPtr[2] = paletteEntryPtr[2];
     } while (pixelBufferOffset != 0xc00);
     goto LAB_0025e78c;
   }
   if ((frameFormatType & 0x7f) == 2) {
     if (*(void **)(decoderState + 0x10) != (void *)0x0) {
       free(*(void **)(decoderState + 0x10));
       decoderState[0x10] = 0;
       decoderState[0x11] = 0;
       decoderState[0x12] = 0;
       decoderState[0x13] = 0;
     }
     memcpy(pixelBuffer,frameData + 8,0xc00);
     bitstreamOffset = 8;
     bitsPerIndexUint = 0x18;
     goto LAB_0025e78c;
   }
   currentPaletteCount = *(ushort *)(frameData + 6);
   existingPaletteBuffer = *(char **)(decoderState + 0x10);
   paletteAllocSize = 0x100;
   if (0x7f < currentPaletteCount) {
     paletteAllocSize = currentPaletteCount + 0x100;
   }
   *decoderState = currentPaletteCount;
   if (existingPaletteBuffer == (char *)0x0) {
 LAB_0025e89c:
     decoderState[1] = paletteAllocSize;
     existingPaletteBuffer = (char *)malloc(((ulong)paletteAllocSize + (ulong)paletteAllocSize * 2) * 2);
     *(char **)(decoderState + 0x10) = existingPaletteBuffer;
   }
   else if (decoderState[1] != paletteAllocSize) {
     free(existingPaletteBuffer);
     currentPaletteCount = *decoderState;
     goto LAB_0025e89c;
   }
   paletteEntryCounter = (uint)currentPaletteCount;
   if (paletteEntryCounter == 0) {
     paletteEntryCount = 0;
   }
   else {
     paletteDataStart = frameData + 8;
     paletteEntryCount = (ulong)paletteEntryCounter;
     if ((paletteEntryCounter < 8) || ((existingPaletteBuffer < frameData + paletteEntryCount * 3 + 8 && (paletteDataStart < existingPaletteBuffer + paletteEntryCount * 3)))) {
       alignedPaletteSize = 0;
     }
     else {
       if (paletteEntryCounter < 0x10) {
         paletteCopySize = 0;
       }
       else {
         alignedPaletteSize = paletteEntryCount & 0xfff0;
         paletteCopySize = alignedPaletteSize;
         paletteWriteCursor = (undefined8 *)existingPaletteBuffer;
         paletteReadCursor = paletteDataStart;
         do {
           paletteChunk2 = *(undefined8 *)(paletteReadCursor + 0x10);
           paletteChunk1 = *(undefined8 *)(paletteReadCursor + 0x28);
           paletteChunk0 = *(undefined8 *)(paletteReadCursor + 0x20);
           paletteCopySize = paletteCopySize - 0x10;
           paletteChunk4 = *(undefined8 *)(paletteReadCursor + 8);
           paletteChunk3 = *(undefined8 *)paletteReadCursor;
           *(undefined8 *)(paletteWriteCursor + 0x18) = *(undefined8 *)(paletteReadCursor + 0x18);
           *(undefined8 *)(paletteWriteCursor + 0x10) = paletteChunk2;
           *(undefined8 *)(paletteWriteCursor + 0x28) = paletteChunk1;
           *(undefined8 *)(paletteWriteCursor + 0x20) = paletteChunk0;
           *(undefined8 *)(paletteWriteCursor + 8) = paletteChunk4;
           *(undefined8 *)paletteWriteCursor = paletteChunk3;
           paletteWriteCursor = paletteWriteCursor + 0x30;
           paletteReadCursor = paletteReadCursor + 0x30;
         } while (paletteCopySize != 0);
         if (alignedPaletteSize == paletteEntryCount) goto LAB_0025e944;
         paletteCopySize = alignedPaletteSize;
         if ((currentPaletteCount >> 3 & 1) == 0) goto LAB_0025e8ec;
       }
       alignedPaletteSize = paletteEntryCount & 0xfff8;
       paletteCopyBytes = paletteCopySize - alignedPaletteSize;
       paletteCopySize = paletteCopySize * 3;
       do {
         paletteWriteCursor = (undefined8 *)(existingPaletteBuffer + paletteCopySize);
         paletteReadCursor = paletteDataStart + (paletteCopySize & 0xfffffff8);
         paletteCopySize = paletteCopySize + 0x18;
         paletteCopyBytes = paletteCopyBytes + 8;
         paletteChunk1 = *(undefined8 *)(paletteReadCursor + 8);
         paletteChunk0 = *(undefined8 *)paletteReadCursor;
         *(undefined8 *)(paletteWriteCursor + 0x10) = *(undefined8 *)(paletteReadCursor + 0x10);
         *(undefined8 *)(paletteWriteCursor + 8) = paletteChunk1;
         *(undefined8 *)paletteWriteCursor = paletteChunk0;
       } while (paletteCopyBytes != 0);
       if (alignedPaletteSize == paletteEntryCount) goto LAB_0025e944;
     }
 LAB_0025e8ec:
     paletteCopyBytes = paletteEntryCount - alignedPaletteSize;
     alignedPaletteSize = alignedPaletteSize * 3;
     do {
       paletteWriteCursor = (undefined8 *)(existingPaletteBuffer + alignedPaletteSize);
       paletteCopyOffset = (int)alignedPaletteSize;
       paletteCopyBytes = paletteCopyBytes + -1;
       *((char *)paletteWriteCursor) = paletteDataStart[alignedPaletteSize & 0xffffffff];
       alignedPaletteSize = alignedPaletteSize + 3;
       ((char *)paletteWriteCursor)[1] = paletteDataStart[paletteCopyOffset + 1];
       ((char *)paletteWriteCursor)[2] = paletteDataStart[paletteCopyOffset + 2];
     } while (paletteCopyBytes != 0);
   }
 LAB_0025e944:
   bitstreamOffset = paletteEntryCounter * 3 + 8;
   pixelBufferOffset = 0;
   bitCursor = 0;
   bitsPerIndex = (&gdivoom_image_bits_table)[paletteEntryCount];
   bitsPerIndexUint = (uint)bitsPerIndex;
   bitstreamOffsetUshort = (ushort)bitstreamOffset;
   do {
     bitOffset = bitCursor & 7;
     byteOffset = (ulong)(bitCursor >> 3);
     totalBits = bitOffset + bitsPerIndex;
     if (totalBits < 9) {
       paletteIndex = ((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort] << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                (ulong)((8 - totalBits) + bitOffset & 0x1f);
     }
     else {
       paletteIndex = (((uint)(byte)frameData[byteOffset + bitstreamOffsetUshort + 1] << (ulong)(0x10 - totalBits & 0x1f) & 0xff) >>
                (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                (uint)((byte)frameData[byteOffset + bitstreamOffsetUshort] >> (ulong)bitOffset);
     }
     outputPixelPtr = (undefined1 *)((long)pixelBuffer + pixelBufferOffset);
     bitCursor = bitCursor + bitsPerIndex;
     pixelBufferOffset = pixelBufferOffset + 3;
     paletteEntryPtr = (undefined1 *)(*(long *)(decoderState + 0x10) + (ulong)(paletteIndex & 0xffff) * 3);
     *outputPixelPtr = *paletteEntryPtr;
     outputPixelPtr[1] = paletteEntryPtr[1];
     outputPixelPtr[2] = paletteEntryPtr[2];
   } while (pixelBufferOffset != 0xc00);
 LAB_0025e78c:
   if (bytesConsumed == (int *)0x0) {
     return 1;
   }
   *bytesConsumed = bitsPerIndexUint * 0x80 + (bitstreamOffset & 0xffff);
   return 1;
 }
 
 
 undefined1 *
 divoom_image_decode_decode_one_fix
           (char *frameData,undefined8 pixelBuffer,uint *bytesConsumed,undefined2 *frameDelay)
 
 {
   ushort paletteSize;
   short bytesDecoded;
   short blockBytesDecoded;
   short *decoderState;
   char *errorMessage;
   undefined8 errorCode;
   ushort bitstreamOffset;
   
   if (frameData == (char *)0x0) {
     errorCode = 0x1499;
     errorMessage = "err: %d!\n";
   }
   else {
     if (*frameData == -0x56) {
       if ((frameData[5] & 0x7fU) != 0x15) {
         printf("image size err: %d: %d!\n",0x14a4);
         return (undefined1 *)0x0;
       }
       if (frameDelay != (undefined2 *)0x0) {
         *frameDelay = *(undefined2 *)(frameData + 3);
       }
       decoderState = (short *)malloc(0x820);
       if (decoderState != (short *)0x0) {
         memset(decoderState + 1,0,0x40e);
         paletteSize = *(short *)(frameData + 6);
         *(char **)(decoderState + 4) = frameData + 8;
         bitstreamOffset = paletteSize * 3 + 8;
         *decoderState = paletteSize;
         blockBytesDecoded = divoom_image_decode_decode_fix_64(decoderState,frameData + bitstreamOffset,pixelBuffer,0,0);
         bitstreamOffset = bitstreamOffset + blockBytesDecoded;
         blockBytesDecoded = divoom_image_decode_decode_fix_64(decoderState,frameData + bitstreamOffset,pixelBuffer,1,0);
         bitstreamOffset = bitstreamOffset + blockBytesDecoded;
         blockBytesDecoded = divoom_image_decode_decode_fix_64(decoderState,frameData + bitstreamOffset,pixelBuffer,0,1);
         bitstreamOffset = bitstreamOffset + blockBytesDecoded;
         blockBytesDecoded = divoom_image_decode_decode_fix_64(decoderState,frameData + bitstreamOffset,pixelBuffer,1,1);
         if (bytesConsumed != (uint *)0x0) {
           *bytesConsumed = (uint)(ushort)(bitstreamOffset + blockBytesDecoded);
         }
         free(decoderState);
         return &DAT_00000001;
       }
       return (undefined1 *)0x0;
     }
     errorCode = 0x149e;
     errorMessage = "image flag err: %d!\n";
   }
   printf(errorMessage,errorCode);
   return (undefined1 *)0x0;
 }
 
 
 void divoom_image_decode_decode_pass_review(long decoderStateAddress)
 
 {
   char *frameHeader;
   byte frameFormatType;
   uint frameSize;
   uint currentOffset;
   
   currentOffset = *(uint *)(decoderStateAddress + 0xc);
   if (currentOffset < *(uint *)(decoderStateAddress + 4)) {
     do {
       frameHeader = (char *)(*(long *)(decoderStateAddress + 0x10) + (ulong)currentOffset);
       if (*frameHeader == -0x56) {
         frameFormatType = frameHeader[5];
         if (frameFormatType < 0x11) {
           frameSize = 1 << (ulong)(frameFormatType & 0x1f);
           if ((frameSize & 0x6e0) != 0) goto LAB_0025ecd8;
           if ((frameSize & 0x1f801) != 0) {
             return;
           }
         }
         if (-1 < (char)frameFormatType) {
           return;
         }
       }
 LAB_0025ecd8:
       currentOffset = *(ushort *)(frameHeader + 1) + currentOffset;
       *(uint *)(decoderStateAddress + 0xc) = currentOffset;
     } while (currentOffset < *(uint *)(decoderStateAddress + 4));
   }
   return;
 }
 
 
 void divoom_image_decode_decode_pic(long decoderStateAddress,undefined8 pixelBuffer,undefined8 userContext)
 
 {
   uint currentOffset;
   byte frameFormatType;
   long threadLocalStorage;
   int bytesConsumed;
   int decodeResult;
   undefined8 errorCode;
   ulong currentOffsetUlong;
   long frameDataBase;
   int stackCheck;
   long stackCheckValue;
   
   threadLocalStorage = tpidr_el0;
   stackCheckValue = *(long *)(threadLocalStorage + 0x28);
   stackCheck = 0;
   if (decoderStateAddress == 0) {
     errorCode = 0x191c;
   }
   else {
     currentOffset = *(uint *)(decoderStateAddress + 0xc);
     currentOffsetUlong = (ulong)currentOffset;
     if (currentOffset < *(uint *)(decoderStateAddress + 4)) {
       frameDataBase = *(long *)(decoderStateAddress + 0x10);
       frameFormatType = *(byte *)(frameDataBase + (ulong)(currentOffset + 5));
       currentOffset = frameFormatType & 0x7f;
       if (currentOffset < 2) {
         decodeResult = divoom_image_decode_decode_one(decoderStateAddress,frameDataBase + currentOffsetUlong,pixelBuffer,&stackCheck);
         decodeResult = (uint)(decodeResult != 0) << 4;
       }
       else if (currentOffset - 2 < 3) {
         decodeResult = divoom_image_decode_decode_one_big(decoderStateAddress,frameDataBase + currentOffsetUlong,pixelBuffer,&stackCheck);
         decodeResult = (uint)(decodeResult != 0) << 5;
       }
       else if (currentOffset - 0xb < 6) {
         decodeResult = divoom_image_decode_decode_one_64(decoderStateAddress,frameDataBase + currentOffsetUlong,pixelBuffer,&stackCheck);
         decodeResult = (uint)(decodeResult != 0) << 6;
       }
       else if ((((frameFormatType & 0x7e) == 0x12) || ((frameFormatType & 0x7b) == 0x11)) || (currentOffset == 0x14)) {
         bytesConsumed = divoom_image_decode_decode_one_128(decoderStateAddress,frameDataBase + currentOffsetUlong,pixelBuffer,&stackCheck,userContext);
         decodeResult = 0;
         if (bytesConsumed != 0) {
           decodeResult = -0x80;
         }
       }
       else {
         decodeResult = 0;
       }
       *(int *)(decoderStateAddress + 0xc) = *(int *)(decoderStateAddress + 0xc) + stackCheck;
       goto LAB_0025f9cc;
     }
     errorCode = 0x1922;
   }
   printf("err: %d!\n",errorCode);
   decodeResult = 0;
 LAB_0025f9cc:
   if (*(long *)(threadLocalStorage + 0x28) != stackCheckValue) {
                     /* WARNING: Subroutine does not return */
     __stack_chk_fail(decodeResult);
   }
   return;
 }
 
 
 bool divoom_image_decode_decode_word(long decoderStateAddress)
 
 {
   ushort wordLength;
   
   wordLength = divoom_image_decode_get_word_info
                     (*(long *)(decoderStateAddress + 0x10) + (ulong)*(uint *)(decoderStateAddress + 0xc));
   *(uint *)(decoderStateAddress + 0xc) = *(int *)(decoderStateAddress + 0xc) + (uint)wordLength;
   return wordLength != 0;
 }
 
 
 void divoom_image_decode_destoy(void *decoderHandle)
 
 {
   if (decoderHandle != (void *)0x0) {
     if (*(void **)((long)decoderHandle + 0x18) != (void *)0x0) {
       free(*(void **)((long)decoderHandle + 0x18));
     }
     if (*(void **)((long)decoderHandle + 0x20) != (void *)0x0) {
       free(*(void **)((long)decoderHandle + 0x20));
     }
     free(decoderHandle);
     return;
   }
   return;
 }
 
 
 undefined2 divoom_image_decode_get_active_time_info(long decoderStateAddress)
 
 {
   return *(undefined2 *)(decoderStateAddress + 3);
 }
 
 
 void divoom_image_decode_get_all_frame_exit(void *decoderHandle)
 
 {
   if (decoderHandle != (void *)0x0) {
     free(decoderHandle);
     return;
   }
   return;
 }
 
 
 void * divoom_image_decode_get_all_frame_init(undefined8 userContext,undefined4 streamLength)
 
 {
   void *decoderHandle;
   
   decoderHandle = malloc(0x5c460);
   if (decoderHandle != (void *)0x0) {
     memset(decoderHandle,0,0x2e230);
     *(undefined4 *)((long)decoderHandle + 4) = streamLength;
     *(undefined8 *)((long)decoderHandle + 8) = userContext;
   }
   return decoderHandle;
 }
 
 
 uint * divoom_image_decode_get_all_frame_next(uint *decoderState)
 
 {
   char *frameHeader;
   byte frameFormatType;
   short frameDelay;
   uint frameSizeMask;
   undefined1 decodeStatus;
   undefined8 *decoderHandle;
   uint *frameBuffer;
   uint currentOffset;
   
   if ((decoderState == (uint *)0x0) || (currentOffset = *decoderState, decoderState[1] <= currentOffset)) {
     frameBuffer = (uint *)0x0;
   }
   else {
     frameBuffer = decoderState + 4;
     memset(frameBuffer,0,0x2e21c);
     decoderHandle = (undefined8 *)malloc(0x50);
     if (decoderHandle != (undefined8 *)0x0) {
       decoderHandle[4] = 0;
       decoderHandle[1] = 0;
       *decoderHandle = 0;
       decoderHandle[3] = 0;
       decoderHandle[2] = 0;
     }
     do {
       frameHeader = (char *)(*(long *)(decoderState + 2) + (ulong)currentOffset);
       currentOffset = (uint)*(ushort *)(frameHeader + 1);
       if (*frameHeader == -0x56) {
         frameFormatType = frameHeader[5];
         if (frameFormatType < 0x11) {
           frameSizeMask = 1 << (ulong)(frameFormatType & 0x1f);
           if ((frameSizeMask & 0x1f801) != 0) goto LAB_00260aa8;
           if ((frameSizeMask & 0x4c0) == 0) {
             if ((frameSizeMask & 0x220) == 0) goto LAB_00260b14;
             if (*(char *)((long)decoderState + 0x12) != '\0') break;
             if (8 < currentOffset) {
               divoom_image_decode_get_word_info(frameHeader,(long)decoderState + 0x2d016);
               *(undefined1 *)((long)decoderState + 0x11) = 1;
             }
           }
         }
         else {
 LAB_00260b14:
           if (-1 < (char)frameFormatType) {
 LAB_00260aa8:
             frameDelay = *(short *)(frameHeader + 3);
             if ((*(char *)((long)decoderState + 0x12) != '\0') && (frameDelay != (short)decoderState[5])) break;
             if (decoderHandle != (undefined8 *)0x0) {
               if ((void *)decoderHandle[3] != (void *)0x0) {
                 free((void *)decoderHandle[3]);
                 decoderHandle[3] = 0;
               }
               *(uint *)((long)decoderHandle + 4) = currentOffset;
               *(undefined4 *)((long)decoderHandle + 0xc) = 0;
               decoderHandle[2] = frameHeader;
             }
             decodeStatus = divoom_image_decode_decode_pic
                               (decoderHandle,(long)decoderState +
                                      (ulong)*(byte *)((long)decoderState + 0x12) * 0xc00 + 0x16,
                                decoderState + 5);
             *(undefined1 *)(decoderState + 4) = decodeStatus;
             *(short *)(decoderState + 5) = frameDelay;
             *(char *)((long)decoderState + 0x12) = *(char *)((long)decoderState + 0x12) + '\x01';
             if (frameDelay == 0) {
               *decoderState = *decoderState + currentOffset;
               break;
             }
           }
         }
       }
       currentOffset = *decoderState + currentOffset;
       *decoderState = currentOffset;
     } while (currentOffset < decoderState[1]);
     if (decoderHandle != (undefined8 *)0x0) {
       if ((void *)decoderHandle[3] != (void *)0x0) {
         free((void *)decoderHandle[3]);
       }
       if ((void *)decoderHandle[4] != (void *)0x0) {
         free((void *)decoderHandle[4]);
       }
       free(decoderHandle);
     }
   }
   return frameBuffer;
 }
 
 
 undefined1 divoom_image_decode_get_effect_type(long decoderStateAddress)
 
 {
   if (*(char *)(decoderStateAddress + 5) == '\n' || *(char *)(decoderStateAddress + 5) == '\x06') {
     return *(undefined1 *)(decoderStateAddress + 8);
   }
   return 0;
 }
 
 
 undefined8 divoom_image_decode_get_image_info(char *frameHeader,byte *formatTypeOut)
 
 {
   char frameFormatByte;
   undefined8 imageSize;
   byte formatType;
   
   if (*frameHeader != -0x56) {
     imageSize = 0;
     if (formatTypeOut == (byte *)0x0) {
       return 0;
     }
     formatType = 6;
     goto LAB_0025a200;
   }
   frameFormatByte = frameHeader[5];
   switch(frameFormatByte) {
   case '\0':
     imageSize = 0x10;
     goto joined_r0x0025a1e8;
   default:
     if (formatTypeOut == (byte *)0x0) {
       return 0x20;
     }
     if (frameFormatByte == '\x05') {
       imageSize = 0x20;
       formatType = 2;
     }
     else {
       imageSize = 0x20;
       formatType = frameFormatByte >> 7 & 3;
     }
     break;
   case '\x06':
     imageSize = 0x20;
     goto joined_r0x0025a25c;
   case '\a':
     imageSize = 0x10;
     if (formatTypeOut == (byte *)0x0) {
       return 0x10;
     }
     formatType = 5;
     break;
   case '\t':
     imageSize = 0x40;
     if (formatTypeOut == (byte *)0x0) {
       return 0x40;
     }
     formatType = 2;
     break;
   case '\n':
     imageSize = 0x40;
 joined_r0x0025a25c:
     if (formatTypeOut == (byte *)0x0) {
       return imageSize;
     }
     formatType = 4;
     break;
   case '\v':
   case '\f':
   case '\r':
   case '\x0e':
   case '\x0f':
   case '\x10':
     imageSize = 0x40;
 joined_r0x0025a1e8:
     if (formatTypeOut == (byte *)0x0) {
       return imageSize;
     }
     formatType = 0;
   }
 LAB_0025a200:
   *formatTypeOut = formatType;
   return imageSize;
 }
 
 
 long divoom_image_decode_get_pic_data(long decoderStateAddress,ushort *frameLengthOut,undefined2 *frameDelayOut)
 
 {
   long frameHeaderAddress;
   uint currentOffset;
   ushort frameLength;
   
   if (decoderStateAddress != 0) {
     currentOffset = *(uint *)(decoderStateAddress + 0xc);
     if (currentOffset < *(uint *)(decoderStateAddress + 4)) {
       frameHeaderAddress = *(long *)(decoderStateAddress + 0x10) + (ulong)currentOffset;
       frameLength = *(ushort *)(frameHeaderAddress + 1);
       if (frameLengthOut != (ushort *)0x0) {
         *frameLengthOut = frameLength;
       }
       if (frameDelayOut != (undefined2 *)0x0) {
         *frameDelayOut = *(undefined2 *)(frameHeaderAddress + 3);
       }
       *(uint *)(decoderStateAddress + 0xc) = currentOffset + frameLength;
       return frameHeaderAddress;
     }
   }
   return 0;
 }
 
 
 undefined2 divoom_image_decode_get_pic_len(long decoderStateAddress)
 
 {
   return *(undefined2 *)(decoderStateAddress + 1);
 }
 
 
 undefined8 divoom_image_decode_get_pic_width(long decoderStateAddress)
 
 {
   undefined8 picWidth;
   
   picWidth = 0x10;
   switch(*(undefined1 *)(decoderStateAddress + 5)) {
   case 0:
     goto switchD_00260924_caseD_0;
   default:
     picWidth = 0x80;
 switchD_00260924_caseD_0:
     return picWidth;
   case 2:
   case 3:
     return 0x20;
   case 0xb:
   case 0xc:
     return 0x40;
   }
 }
 
 
 short divoom_image_decode_get_time_info(long decoderStateAddress)
 
 {
   short frameDelay;
   
   frameDelay = 500;
   if (*(short *)(decoderStateAddress + 3) != 0) {
     frameDelay = *(short *)(decoderStateAddress + 3);
   }
   return frameDelay;
 }
 
 
 uint divoom_image_decode_get_word_info(long frameHeaderAddress,undefined1 *wordInfoOut)
 
 {
   byte formatType;
   ushort stringLength;
   int stringBytes;
   uint frameLength;
   
   if (*(char *)(frameHeaderAddress + 5) == '\x05') {
     frameLength = (uint)*(ushort *)(frameHeaderAddress + 1);
     if (wordInfoOut != (undefined1 *)0x0) {
       if (*(ushort *)(frameHeaderAddress + 1) == 8) {
         memset(wordInfoOut,0,0x1216);
         frameLength = 8;
       }
       else {
         *wordInfoOut = *(undefined1 *)(frameHeaderAddress + 8);
         wordInfoOut[1] = *(undefined1 *)(frameHeaderAddress + 9);
         wordInfoOut[2] = *(undefined1 *)(frameHeaderAddress + 10);
         wordInfoOut[3] = *(undefined1 *)(frameHeaderAddress + 0xb);
         wordInfoOut[4] = *(undefined1 *)(frameHeaderAddress + 0xc);
         wordInfoOut[6] = *(undefined1 *)(frameHeaderAddress + 0xd);
         wordInfoOut[8] = *(undefined1 *)(frameHeaderAddress + 0xe);
         *(undefined2 *)(wordInfoOut + 10) = *(undefined2 *)(frameHeaderAddress + 0xf);
         wordInfoOut[0xc] = *(undefined1 *)(frameHeaderAddress + 0x11);
         wordInfoOut[0xd] = *(undefined1 *)(frameHeaderAddress + 0x12);
         wordInfoOut[0xe] = *(undefined1 *)(frameHeaderAddress + 0x13);
         stringLength = *(ushort *)(frameHeaderAddress + 0x14);
         *(ushort *)(wordInfoOut + 0x12) = stringLength;
         memcpy(wordInfoOut + 0x14,(void *)(frameHeaderAddress + 0x16),(ulong)stringLength << 1);
         stringBytes = (uint)*(ushort *)(wordInfoOut + 0x12) * 2;
         *(undefined2 *)(wordInfoOut + 0x14 + (ulong)*(ushort *)(wordInfoOut + 0x12) * 2) = 0;
         frameLength = stringBytes + 0x18;
         formatType = *(byte *)(frameHeaderAddress + ((ulong)(stringBytes + 0x16) & 0xfffe));
         wordInfoOut[0x114] = formatType;
         memcpy(wordInfoOut + 0x116,(void *)(frameHeaderAddress + ((ulong)frameLength & 0xfffe)),(ulong)formatType * 0x22);
         frameLength = frameLength + (uint)(byte)wordInfoOut[0x114] * 0x22;
       }
     }
   }
   else {
     frameLength = 0;
   }
   return frameLength;
 }
 
 
 ulong divoom_image_decode_get_word_info2(long frameHeaderAddress,undefined8 *wordInfoOut1,undefined8 *wordInfoOut2)
 
 {
   uint stringBytes1;
   uint stringBytes2;
   undefined8 *outputBuffer;
   char frameFormatType;
   int stringBytes;
   ulong frameLength;
   ushort stringLength;
   
   frameFormatType = *(char *)(frameHeaderAddress + 5);
   if (frameFormatType != '\t' && frameFormatType != '\x05') {
     return 0;
   }
   outputBuffer = wordInfoOut2;
   if (wordInfoOut1 != (undefined8 *)0x0) {
     outputBuffer = wordInfoOut1;
   }
   if ((wordInfoOut1 == (undefined8 *)0x0) && (wordInfoOut2 == (undefined8 *)0x0)) {
     return (ulong)*(ushort *)(frameHeaderAddress + 1);
   }
   if (*(ushort *)(frameHeaderAddress + 1) == 8) {
     if (wordInfoOut1 != (undefined8 *)0x0) {
       wordInfoOut1[0x21] = 0;
       wordInfoOut1[0x20] = 0;
       wordInfoOut1[0x23] = 0;
       wordInfoOut1[0x22] = 0;
       wordInfoOut1[0x1d] = 0;
       wordInfoOut1[0x1c] = 0;
       wordInfoOut1[0x1f] = 0;
       wordInfoOut1[0x1e] = 0;
       wordInfoOut1[0x19] = 0;
       wordInfoOut1[0x18] = 0;
       wordInfoOut1[0x1b] = 0;
       wordInfoOut1[0x1a] = 0;
       wordInfoOut1[0x15] = 0;
       wordInfoOut1[0x14] = 0;
       wordInfoOut1[0x17] = 0;
       wordInfoOut1[0x16] = 0;
       wordInfoOut1[0x11] = 0;
       wordInfoOut1[0x10] = 0;
       wordInfoOut1[0x13] = 0;
       wordInfoOut1[0x12] = 0;
       wordInfoOut1[0xd] = 0;
       wordInfoOut1[0xc] = 0;
       wordInfoOut1[0xf] = 0;
       wordInfoOut1[0xe] = 0;
       wordInfoOut1[9] = 0;
       wordInfoOut1[8] = 0;
       wordInfoOut1[0xb] = 0;
       wordInfoOut1[10] = 0;
       wordInfoOut1[5] = 0;
       wordInfoOut1[4] = 0;
       wordInfoOut1[7] = 0;
       wordInfoOut1[6] = 0;
       wordInfoOut1[1] = 0;
       *wordInfoOut1 = 0;
       wordInfoOut1[3] = 0;
       wordInfoOut1[2] = 0;
       return 8;
     }
     *wordInfoOut2 = 0;
     wordInfoOut2[1] = 0;
     *(undefined4 *)(wordInfoOut2 + 2) = 0;
     return 8;
   }
   *(undefined1 *)outputBuffer = *(undefined1 *)(frameHeaderAddress + 8);
   *(undefined1 *)((long)outputBuffer + 1) = *(undefined1 *)(frameHeaderAddress + 9);
   *(undefined1 *)((long)outputBuffer + 2) = *(undefined1 *)(frameHeaderAddress + 10);
   *(undefined1 *)((long)outputBuffer + 3) = *(undefined1 *)(frameHeaderAddress + 0xb);
   *(undefined1 *)((long)outputBuffer + 4) = *(undefined1 *)(frameHeaderAddress + 0xc);
   if (frameFormatType == '\t') {
     *(undefined1 *)((long)outputBuffer + 5) = *(undefined1 *)(frameHeaderAddress + 0xd);
     *(undefined1 *)((long)outputBuffer + 6) = *(undefined1 *)(frameHeaderAddress + 0xe);
     *(undefined1 *)((long)outputBuffer + 7) = *(undefined1 *)(frameHeaderAddress + 0xf);
     *(undefined2 *)((long)outputBuffer + 10) = *(undefined2 *)(frameHeaderAddress + 0x11);
     *(undefined1 *)((long)outputBuffer + 0xc) = *(undefined1 *)(frameHeaderAddress + 0x13);
     *(undefined1 *)((long)outputBuffer + 0xd) = *(undefined1 *)(frameHeaderAddress + 0x14);
     *(undefined1 *)((long)outputBuffer + 0xe) = *(undefined1 *)(frameHeaderAddress + 0x15);
     *(undefined1 *)((long)outputBuffer + 0xf) = *(undefined1 *)(frameHeaderAddress + 0x16);
     *(undefined1 *)(outputBuffer + 2) = *(undefined1 *)(frameHeaderAddress + 0x17);
     stringLength = *(ushort *)(frameHeaderAddress + 0x18);
     if (wordInfoOut1 == (undefined8 *)0x0) {
       frameLength = 0x18;
 LAB_00260168:
       *(ushort *)((long)outputBuffer + 0x12) = stringLength;
       return frameLength;
     }
     *(ushort *)((long)wordInfoOut1 + 0x14) = stringLength;
     *(ushort *)((long)outputBuffer + 0x12) = stringLength;
     memcpy((void *)((long)wordInfoOut1 + 0x16),(void *)(frameHeaderAddress + 0x1a),(ulong)stringLength << 1);
     stringBytes = (uint)*(ushort *)((long)wordInfoOut1 + 0x14) * 2;
     *(undefined2 *)((long)wordInfoOut1 + 0x16 + (ulong)*(ushort *)((long)wordInfoOut1 + 0x14) * 2) = 0;
     stringBytes1 = stringBytes + 0x1a;
     stringBytes2 = stringBytes + 0x1c;
   }
   else {
     *(undefined1 *)((long)outputBuffer + 6) = *(undefined1 *)(frameHeaderAddress + 0xd);
     *(undefined2 *)((long)outputBuffer + 10) = *(undefined2 *)(frameHeaderAddress + 0xf);
     *(undefined1 *)((long)outputBuffer + 0xc) = *(undefined1 *)(frameHeaderAddress + 0x11);
     *(undefined1 *)((long)outputBuffer + 0xd) = *(undefined1 *)(frameHeaderAddress + 0x12);
     *(undefined1 *)((long)outputBuffer + 0xe) = *(undefined1 *)(frameHeaderAddress + 0x13);
     stringLength = *(ushort *)(frameHeaderAddress + 0x14);
     if (wordInfoOut1 == (undefined8 *)0x0) {
       frameLength = 0x14;
       goto LAB_00260168;
     }
     *(ushort *)((long)wordInfoOut1 + 0x14) = stringLength;
     *(ushort *)((long)outputBuffer + 0x12) = stringLength;
     memcpy((void *)((long)wordInfoOut1 + 0x16),(void *)(frameHeaderAddress + 0x16),(ulong)stringLength << 1);
     stringBytes = (uint)*(ushort *)((long)wordInfoOut1 + 0x14) * 2;
     *(undefined2 *)((long)wordInfoOut1 + 0x16 + (ulong)*(ushort *)((long)wordInfoOut1 + 0x14) * 2) = 0;
     stringBytes1 = stringBytes + 0x16;
     stringBytes2 = stringBytes + 0x18;
   }
   *(undefined1 *)((long)wordInfoOut1 + 0x116) = *(undefined1 *)(frameHeaderAddress + ((ulong)stringBytes1 & 0xfffe));
   wordInfoOut1[0x23] = frameHeaderAddress + ((ulong)stringBytes2 & 0xfffe);
   return (ulong)stringBytes2;
 }
 
 
 undefined8 divoom_image_decode_Iframe(undefined8 userContext,void *outputBuffer,uint imageSize)
 
 {
   int pixelCount;
   uint decodeResult;
   void *tempBuffer;
   
   pixelCount = (imageSize & 0xff) * (imageSize & 0xff);
   tempBuffer = malloc((ulong)(uint)(pixelCount * 6));
   decodeResult = divoom_image_decode_Iframe_in(userContext,tempBuffer,imageSize);
   if ((decodeResult & 0xfe) == 0x14) {
     divoom_image_encode_convert_rgb_local_to_net_128(tempBuffer,outputBuffer);
   }
   else {
     memcpy(outputBuffer,tempBuffer,(ulong)(uint)(pixelCount * 3));
   }
   free(tempBuffer);
   return 1;
 }
 
 
 uint divoom_image_decode_Iframe_in(long frameHeaderAddress,undefined1 *pixelBuffer,byte imageSize)
 
 {
   long bitstreamStart;
   undefined1 *outputPixelPtr;
   undefined1 *paletteEntryPtr;
   uint bitOffset;
   byte frameFormatType;
   byte bitsPerIndex;
   undefined2 rgb565Pair;
   bool continueLoop;
   ulong pixelIndex;
   ulong byteOffset;
   uint bitsPerIndexUint;
   ushort pixelCounter;
   short pixelIndexShort;
   long pixelBufferOffset;
   uint bitCursor;
   ulong bitstreamByteOffset;
   uint paletteIndex;
   uint totalBits;
   
   frameFormatType = *(byte *)(frameHeaderAddress + 5);
   if (frameFormatType == 0) {
     bitstreamStart = (ulong)*(byte *)(frameHeaderAddress + 6) * 3 + 7;
     bitsPerIndex = (&gdivoom_image_bits_table)[*(byte *)(frameHeaderAddress + 6)];
     bitsPerIndexUint = (uint)bitsPerIndex;
     if (imageSize < 0x40) {
       if (imageSize == 0x10) {
         pixelBufferOffset = 0;
         bitCursor = 0;
         bitstreamStart = frameHeaderAddress + bitstreamStart;
         do {
           bitOffset = bitCursor & 7;
           byteOffset = (ulong)(bitCursor >> 3);
           totalBits = bitOffset + bitsPerIndexUint;
           if (totalBits < 9) {
             paletteIndex = ((uint)*(byte *)(bitstreamStart + byteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                      (ulong)((8 - totalBits) + bitOffset & 0x1f);
           }
           else {
             paletteIndex = (((uint)*(byte *)(bitstreamStart + byteOffset + 1) << (ulong)(0x10 - totalBits & 0x1f) & 0xff)
                      >> (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                      (uint)(*(byte *)(bitstreamStart + byteOffset) >> (ulong)bitOffset);
           }
           outputPixelPtr = pixelBuffer + pixelBufferOffset;
           bitCursor = bitCursor + bitsPerIndexUint;
           pixelBufferOffset = pixelBufferOffset + 3;
           paletteEntryPtr = (undefined1 *)(frameHeaderAddress + 7 + (ulong)(paletteIndex & 0xffff) * 3);
           rgb565Pair = *(undefined2 *)(paletteEntryPtr + 1);
           *outputPixelPtr = *paletteEntryPtr;
           *(undefined2 *)(outputPixelPtr + 1) = rgb565Pair;
         } while (pixelBufferOffset != 0x300);
       }
       else if (imageSize == 0x20) {
         pixelCounter = 0;
         byteOffset = 0;
         bitstreamStart = frameHeaderAddress + bitstreamStart;
         do {
           bitCursor = 0;
           do {
             bitstreamByteOffset = ((byteOffset & 0xfffffffe) * 8 + (ulong)(bitCursor >> 1)) * (ulong)bitsPerIndex;
             bitOffset = (uint)bitstreamByteOffset & 7;
             bitstreamByteOffset = bitstreamByteOffset >> 3;
             totalBits = bitOffset + bitsPerIndexUint;
             if (totalBits < 9) {
               paletteIndex = ((uint)*(byte *)(bitstreamStart + bitstreamByteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                        (ulong)((8 - totalBits) + bitOffset & 0x1f);
             }
             else {
               paletteIndex = (((uint)*(byte *)(bitstreamStart + (bitstreamByteOffset & 0xffffffff) + 1) <<
                          (ulong)(0x10 - totalBits & 0x1f) & 0xff) >> (ulong)(0x10 - totalBits & 0x1f)) <<
                        (ulong)(8 - bitOffset & 0x1f) |
                        (uint)(*(byte *)(bitstreamStart + bitstreamByteOffset) >> (ulong)bitOffset);
             }
             pixelIndex = (ulong)pixelCounter;
             byteOffset = (ulong)pixelCounter;
             outputPixelPtr = (undefined1 *)(frameHeaderAddress + 7 + (ulong)(paletteIndex & 0xffff) * 3);
             continueLoop = bitCursor < 0x1f;
             pixelCounter = pixelCounter + 1;
             rgb565Pair = *(undefined2 *)(outputPixelPtr + 1);
             pixelBuffer[pixelIndex + byteOffset * 2] = *outputPixelPtr;
             *(undefined2 *)(pixelBuffer + pixelIndex + byteOffset * 2 + 1) = rgb565Pair;
             bitCursor = bitCursor + 1;
           } while (continueLoop);
           bitCursor = (uint)byteOffset;
           byteOffset = (ulong)(bitCursor + 1);
         } while (bitCursor < 0x1f);
       }
     }
     else if (imageSize == 0x40) {
       pixelIndexShort = 0;
       bitstreamStart = frameHeaderAddress + bitstreamStart;
       bitCursor = 0;
       do {
         paletteIndex = 0;
         do {
           totalBits = ((bitCursor & 0x3ffffffc) * 4 + (paletteIndex >> 2)) * bitsPerIndexUint;
           bitOffset = totalBits & 7;
           bitstreamByteOffset = (ulong)(totalBits >> 3);
           totalBits = bitOffset + bitsPerIndexUint;
           if (totalBits < 9) {
             totalBits = ((uint)*(byte *)(bitstreamStart + bitstreamByteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                      (ulong)((8 - totalBits) + bitOffset & 0x1f);
           }
           else {
             totalBits = (((uint)*(byte *)(bitstreamStart + bitstreamByteOffset + 1) << (ulong)(0x10 - totalBits & 0x1f) & 0xff)
                      >> (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                      (uint)(*(byte *)(bitstreamStart + bitstreamByteOffset) >> (ulong)bitOffset);
           }
           pixelCounter = pixelIndexShort * 3;
           continueLoop = paletteIndex < 0x3f;
           outputPixelPtr = (undefined1 *)(frameHeaderAddress + 7 + (ulong)(totalBits & 0xffff) * 3);
           pixelIndexShort = pixelIndexShort + 1;
           rgb565Pair = *(undefined2 *)(outputPixelPtr + 1);
           pixelBuffer[pixelCounter] = *outputPixelPtr;
           *(undefined2 *)(pixelBuffer + pixelCounter + 1) = rgb565Pair;
           paletteIndex = paletteIndex + 1;
         } while (continueLoop);
         continueLoop = bitCursor < 0x3f;
         bitCursor = bitCursor + 1;
       } while (continueLoop);
     }
     else if (imageSize == 0x80) {
       pixelIndexShort = 0;
       bitstreamStart = frameHeaderAddress + bitstreamStart;
       bitCursor = 0;
       do {
         paletteIndex = 0;
         do {
           bitstreamByteOffset = (((ulong)(bitCursor << 1) & 0x7ff0) + (ulong)(paletteIndex >> 3)) * (ulong)bitsPerIndex;
           bitOffset = (uint)bitstreamByteOffset & 7;
           bitstreamByteOffset = bitstreamByteOffset >> 3;
           totalBits = bitOffset + bitsPerIndexUint;
           if (totalBits < 9) {
             totalBits = ((uint)*(byte *)(bitstreamStart + bitstreamByteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                      (ulong)((8 - totalBits) + bitOffset & 0x1f);
           }
           else {
             totalBits = (((uint)*(byte *)(bitstreamStart + (bitstreamByteOffset & 0xffffffff) + 1) <<
                        (ulong)(0x10 - totalBits & 0x1f) & 0xff) >> (ulong)(0x10 - totalBits & 0x1f)) <<
                      (ulong)(8 - bitOffset & 0x1f) | (uint)(*(byte *)(bitstreamStart + bitstreamByteOffset) >> (ulong)bitOffset);
           }
           pixelCounter = pixelIndexShort * 3;
           continueLoop = paletteIndex < 0x7f;
           outputPixelPtr = (undefined1 *)(frameHeaderAddress + 7 + (ulong)(totalBits & 0xffff) * 3);
           pixelIndexShort = pixelIndexShort + 1;
           rgb565Pair = *(undefined2 *)(outputPixelPtr + 1);
           pixelBuffer[pixelCounter] = *outputPixelPtr;
           *(undefined2 *)(pixelBuffer + pixelCounter + 1) = rgb565Pair;
           paletteIndex = paletteIndex + 1;
         } while (continueLoop);
         continueLoop = bitCursor < 0x7f;
         bitCursor = bitCursor + 1;
       } while (continueLoop);
     }
   }
   else if (imageSize == 0x10) {
     printf("err out iframe!: %d\n",0x19d4);
   }
   else {
     switch(frameFormatType) {
     case 2:
       memcpy(pixelBuffer,(void *)(frameHeaderAddress + 8),0xc00);
       break;
     case 3:
       pixelBufferOffset = 0;
       bitCursor = 0;
       bitsPerIndex = (&gdivoom_image_bits_table)[*(ushort *)(frameHeaderAddress + 6)];
       bitstreamStart = frameHeaderAddress + (ulong)(ushort)(*(ushort *)(frameHeaderAddress + 6) * 3 + 8);
       do {
         bitOffset = bitCursor & 7;
         byteOffset = (ulong)(bitCursor >> 3);
         totalBits = bitOffset + bitsPerIndex;
         if (totalBits < 9) {
           totalBits = ((uint)*(byte *)(bitstreamStart + byteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                    (ulong)((8 - totalBits) + bitOffset & 0x1f);
         }
         else {
           totalBits = (((uint)*(byte *)(bitstreamStart + byteOffset + 1) << (ulong)(0x10 - totalBits & 0x1f) & 0xff) >>
                    (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                    (uint)(*(byte *)(bitstreamStart + byteOffset) >> (ulong)bitOffset);
         }
         outputPixelPtr = pixelBuffer + pixelBufferOffset;
         bitCursor = bitCursor + bitsPerIndex;
         pixelBufferOffset = pixelBufferOffset + 3;
         paletteEntryPtr = (undefined1 *)(frameHeaderAddress + 8 + (ulong)(totalBits & 0xffff) * 3);
         rgb565Pair = *(undefined2 *)(paletteEntryPtr + 1);
         *outputPixelPtr = *paletteEntryPtr;
         *(undefined2 *)(outputPixelPtr + 1) = rgb565Pair;
       } while (pixelBufferOffset != 0xc00);
       break;
     default:
       printf("err out iframe!: %d, %d\n",0x1a29,(ulong)(uint)frameFormatType);
       break;
     case 0xb:
       memcpy(pixelBuffer,(void *)(frameHeaderAddress + 8),0x3000);
       break;
     case 0xc:
       pixelBufferOffset = 0;
       bitCursor = 0;
       bitsPerIndex = (&gdivoom_image_bits_table)[*(ushort *)(frameHeaderAddress + 6)];
       bitstreamStart = frameHeaderAddress + (ulong)(ushort)(*(ushort *)(frameHeaderAddress + 6) * 3 + 8);
       do {
         bitOffset = bitCursor & 7;
         byteOffset = (ulong)(bitCursor >> 3);
         totalBits = bitOffset + bitsPerIndex;
         if (totalBits < 9) {
           totalBits = ((uint)*(byte *)(bitstreamStart + byteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                    (ulong)((8 - totalBits) + bitOffset & 0x1f);
         }
         else {
           totalBits = (((uint)*(byte *)(bitstreamStart + byteOffset + 1) << (ulong)(0x10 - totalBits & 0x1f) & 0xff) >>
                    (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                    (uint)(*(byte *)(bitstreamStart + byteOffset) >> (ulong)bitOffset);
         }
         outputPixelPtr = pixelBuffer + pixelBufferOffset;
         bitCursor = bitCursor + bitsPerIndex;
         pixelBufferOffset = pixelBufferOffset + 3;
         paletteEntryPtr = (undefined1 *)(frameHeaderAddress + 8 + (ulong)(totalBits & 0xffff) * 3);
         rgb565Pair = *(undefined2 *)(paletteEntryPtr + 1);
         *outputPixelPtr = *paletteEntryPtr;
         *(undefined2 *)(outputPixelPtr + 1) = rgb565Pair;
       } while ((int)pixelBufferOffset != 0x3000);
       break;
     case 0x11:
       memcpy(pixelBuffer,(void *)(frameHeaderAddress + 8),0xc000);
       break;
     case 0x12:
     case 0x14:
       bitCursor = 0;
       pixelCounter = 0;
       bitsPerIndex = (&gdivoom_image_bits_table)[*(ushort *)(frameHeaderAddress + 6)];
       bitstreamStart = frameHeaderAddress + (ulong)(ushort)(*(ushort *)(frameHeaderAddress + 6) * 3 + 8);
       do {
         bitOffset = bitCursor & 7;
         byteOffset = (ulong)(bitCursor >> 3);
         totalBits = bitOffset + bitsPerIndex;
         if (totalBits < 9) {
           totalBits = ((uint)*(byte *)(bitstreamStart + byteOffset) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
                    (ulong)((8 - totalBits) + bitOffset & 0x1f);
         }
         else {
           totalBits = (((uint)*(byte *)(bitstreamStart + byteOffset + 1) << (ulong)(0x10 - totalBits & 0x1f) & 0xff) >>
                    (ulong)(0x10 - totalBits & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
                    (uint)(*(byte *)(bitstreamStart + byteOffset) >> (ulong)bitOffset);
         }
         continueLoop = pixelCounter < 0x3fff;
         bitCursor = bitCursor + bitsPerIndex;
         pixelBufferOffset = (ulong)((totalBits & 0xffff) + (totalBits & 0xffff) * 2) + frameHeaderAddress;
         *pixelBuffer = *(undefined1 *)(pixelBufferOffset + 8);
         pixelBuffer[1] = *(undefined1 *)(pixelBufferOffset + 9);
         pixelCounter = pixelCounter + 1;
         pixelBuffer[2] = *(undefined1 *)(pixelBufferOffset + 10);
         pixelBuffer = pixelBuffer + 3;
       } while (continueLoop);
       break;
     case 0x15:
       divoom_image_decode_decode_one_fix(frameHeaderAddress,pixelBuffer,0,0);
     }
   }
   return (uint)frameFormatType;
 }
 
 
 void divoom_image_decode_reset(long decoderStateAddress)
 
 {
   if (decoderStateAddress != 0) {
     *(undefined4 *)(decoderStateAddress + 0xc) = 0;
   }
   return;
 }
 
 
 void divoom_image_decode_update_time_info(long decoderStateAddress,undefined2 frameDelay)
 
 {
   *(undefined2 *)(decoderStateAddress + 3) = frameDelay;
   return;
 }
 
 
 uint divoom_image_get_bits(uint paletteSize)
 
 {
   uint bitCount;
   uint nextBitCount;
   uint paletteSizeMasked;
   uint bitIndex;
   
   paletteSizeMasked = paletteSize & 0xffff;
   if (0x20 < paletteSizeMasked) {
     if (paletteSizeMasked < 0x101) {
       if (0x80 < (paletteSize & 0xffff)) {
         return 8;
       }
       paletteSizeMasked = 6;
       if (0x40 < (paletteSize & 0xffff)) {
         paletteSizeMasked = 7;
       }
     }
     else {
       paletteSizeMasked = 0xff;
       bitIndex = 0;
       do {
         nextBitCount = bitIndex + 1;
         if (((paletteSizeMasked ^ 0xffffffff) & 0xff) != 0) {
           bitIndex = bitIndex + 1;
         }
         bitCount = paletteSize & 0xffff;
         if ((paletteSize & 1) != 0) {
           paletteSizeMasked = bitIndex;
         }
         paletteSize = paletteSize >> 1 & 0x7fff;
         bitIndex = nextBitCount;
       } while (1 < bitCount);
     }
     return paletteSizeMasked;
   }
   if (0x10 < paletteSizeMasked) {
     return 5;
   }
   if (8 < (paletteSize & 0xffff)) {
     return 4;
   }
   if ((paletteSize & 0xffff) < 5) {
     paletteSizeMasked = 2;
     if ((paletteSize & 0xffff) < 3) {
       paletteSizeMasked = paletteSize - 1;
     }
     return paletteSizeMasked;
   }
   return 3;
 }
 
 
 uint divoom_image_get_dot_info(long bitfieldMap,int bitsPerIndex,uint entryCount)
 
 {
   long byteOffset;
   uint nextBitOffset;
   uint bitIndex;
   uint bitfieldValue;
   uint bitOffset;
   int byteIndex;
   uint bitCount;
   
   entryCount = entryCount & 0xff;
   byteIndex = (int)(entryCount * bitsPerIndex) >> 3;
   bitOffset = entryCount * bitsPerIndex & 7;
   if (8 < entryCount) {
     bitCount = 0;
     bitfieldValue = 0;
     do {
       byteOffset = (long)byteIndex;
       bitIndex = bitCount & 0x1f;
       bitCount = bitCount + 1;
       if (6 < (int)bitOffset) {
         byteIndex = byteIndex + 1;
       }
       nextBitOffset = 0;
       if ((int)bitOffset < 7) {
         nextBitOffset = bitOffset + 1;
       }
       bitfieldValue = -(*(byte *)(bitfieldMap + byteOffset) >> (ulong)(bitOffset & 0x1f) & 1) & 1 << (ulong)bitIndex | bitfieldValue
       ;
       bitOffset = nextBitOffset;
     } while (entryCount != bitCount);
     return bitfieldValue;
   }
   entryCount = bitOffset + entryCount;
   if (8 < entryCount) {
     return (((uint)((byte *)(bitfieldMap + byteIndex))[1] << (ulong)(0x10 - entryCount & 0x1f) & 0xff) >>
            (ulong)(0x10 - entryCount & 0x1f)) << (ulong)(8 - bitOffset & 0x1f) |
            (uint)(*(byte *)(bitfieldMap + byteIndex) >> (ulong)bitOffset);
   }
   return ((uint)*(byte *)(bitfieldMap + byteIndex) << (ulong)(8 - entryCount & 0x1f) & 0xff) >>
          (ulong)((8 - entryCount) + bitOffset & 0x1f);
 }
 
 
 uint divoom_image_get_dot_info_ex(long bitfieldMap,uint bitOffset,byte bitsPerIndex)
 
 {
   uint bitOffsetInByte;
   byte *bytePtr;
   uint totalBits;
   
   bitOffsetInByte = bitOffset & 7;
   totalBits = bitOffsetInByte + bitsPerIndex;
   if (8 < totalBits) {
     bytePtr = (byte *)(bitfieldMap + ((int)bitOffset >> 3));
     return (((uint)bytePtr[1] << (ulong)(0x10 - totalBits & 0x1f) & 0xff) >> (ulong)(0x10 - totalBits & 0x1f)
            ) << (ulong)(8 - bitOffsetInByte & 0x1f) | (uint)(*bytePtr >> (ulong)bitOffsetInByte);
   }
   return ((uint)*(byte *)(bitfieldMap + ((int)bitOffset >> 3)) << (ulong)(8 - totalBits & 0x1f) & 0xff) >>
          (ulong)((8 - totalBits) + bitOffsetInByte & 0x1f);
 }
 
 
 void divoom_image_set_dot_info(long bitfieldMap,int bitsPerIndex,uint entryCount,uint bitfieldValue)
 
 {
   byte currentByte;
   byte bitMask;
   uint bitIndex;
   byte newByte;
   uint bitOffset;
   uint bitCount;
   int byteIndex;
   long byteOffset;
   
   entryCount = entryCount & 0xff;
   if (entryCount != 0) {
     bitCount = 0;
     byteIndex = (int)(entryCount * bitsPerIndex) >> 3;
     bitOffset = entryCount * bitsPerIndex & 7;
     do {
       byteOffset = (long)byteIndex;
       bitIndex = bitCount & 0x1f;
       bitCount = bitCount + 1;
       currentByte = *(byte *)(bitfieldMap + byteOffset);
       bitMask = (byte)(1 << (ulong)(bitOffset & 0x1f));
       newByte = currentByte & (bitMask ^ 0xff);
       if (((bitfieldValue & 0xffff) >> (ulong)bitIndex & 1) != 0) {
         newByte = currentByte | bitMask;
       }
       if (6 < (int)bitOffset) {
         byteIndex = byteIndex + 1;
       }
       bitIndex = 0;
       if ((int)bitOffset < 7) {
         bitIndex = bitOffset + 1;
       }
       *(byte *)(bitfieldMap + byteOffset) = newByte;
       bitOffset = bitIndex;
     } while (entryCount != bitCount);
   }
   return;
 }
 
 
 void divoom_image_set_dot_info_ex(long bitfieldMap,uint bitOffset,byte bitsPerIndex,uint bitfieldValue)
 
 {
   long byteOffset;
   
   byteOffset = (long)((ulong)bitOffset << 0x20) >> 0x23;
   bitOffset = bitOffset & 7;
   *(byte *)(bitfieldMap + byteOffset) =
        *(byte *)(bitfieldMap + byteOffset) | (byte)((bitfieldValue & 0xffff) << (ulong)bitOffset);
   if (8 < bitOffset + bitsPerIndex) {
     *(char *)(byteOffset + bitfieldMap + 1) = (char)((bitfieldValue & 0xffff) >> (ulong)(8 - bitOffset & 0x1f));
   }
   return;
 }
 
 
 undefined8 divoom_multipic_decode(long pixelBuffer,ushort frameIndex,byte *frameData)
 
 {
   bool continueLoop;
   long pixelBufferOffset;
   byte paletteIndexLow;
   byte *paletteData;
   uint bitCursor;
   uint bitCount;
   byte paletteSize;
   byte paletteIndex;
   uint paletteIndexUint;
   undefined8 decodeResult;
   uint bitIndex;
   uint nextBitIndex;
   ulong paletteDataOffset;
   byte bitsPerIndex;
   uint bitsPerIndexUint;
   uint bitOffset;
   ulong byteOffset;
   ushort frameCounter;
   uint bitfieldValue;
   ulong bitfieldByteOffset;
   byte paletteEntryLow;
   ulong paletteEntryOffset;
   
   frameIndex = frameIndex & 0xff;
   if (frameIndex < *frameData) {
     paletteSize = frameData[1];
     bitCursor = ((uint)paletteSize * 3 + 1 >> 1) + 2;
     if (frameIndex != 0) {
       frameCounter = 0;
       do {
         frameCounter = frameCounter + 1;
         bitIndex = 0x7b;
         if (frameData[(ulong)bitCursor & 0xffff] != 0) {
           bitIndex = (uint)frameData[(ulong)bitCursor & 0xffff];
         }
         bitCursor = bitCursor + bitIndex;
       } while (frameCounter < frameIndex);
     }
     paletteDataOffset = (ulong)(bitCursor + 1) & 0xffff;
     paletteIndex = frameData[paletteDataOffset];
     if (paletteIndex == 0) {
       bitsPerIndex = 0xff;
     }
     else {
       bitsPerIndex = 0xff;
       paletteIndexUint = (uint)paletteIndex;
       paletteEntryLow = 0;
       do {
         paletteIndexLow = paletteEntryLow + 1;
         if (bitsPerIndex != 0xff) {
           paletteEntryLow = paletteEntryLow + 1;
         }
         if ((paletteIndexUint & 1) != 0) {
           bitsPerIndex = paletteEntryLow;
         }
         continueLoop = 1 < paletteIndexUint;
         paletteIndexUint = paletteIndexUint >> 1;
         paletteEntryLow = paletteIndexLow;
       } while (continueLoop);
     }
     bitfieldByteOffset = (ulong)(bitCursor + 2) & 0xffff;
     bitCursor = 0;
     paletteData = frameData + 2;
     bitIndex = (uint)bitsPerIndex;
     do {
       if (paletteIndex == 1) {
         bitsPerIndex = frameData[paletteDataOffset + 1];
 LAB_0024b750:
         paletteEntryOffset = (ulong)((uint)bitsPerIndex + (uint)(bitsPerIndex >> 1));
         bitOffset = (uint)(paletteData[paletteEntryOffset] >> 4);
         if ((bitsPerIndex & 1) == 0) {
           bitCount = paletteData[paletteEntryOffset] & 0xf;
           paletteEntryLow = paletteData[paletteEntryOffset + 1] & 0xf;
         }
         else {
           paletteEntryLow = paletteData[paletteEntryOffset + 1];
           bitCount = bitOffset;
 LAB_0024b780:
           bitOffset = paletteEntryLow & 0xf;
           paletteEntryLow = paletteEntryLow >> 4;
         }
       }
       else {
         if (paletteIndex != paletteSize) {
           if (bitIndex == 0) {
             byteOffset = 0;
           }
           else {
             bitCount = 0;
             byteOffset = 0;
             bitOffset = bitCursor * bitIndex >> 3;
             nextBitIndex = bitCursor * bitIndex & 7;
             do {
               bitfieldByteOffset = (ulong)bitOffset;
               paletteIndexUint = bitCount & 0x1f;
               bitfieldValue = nextBitIndex + 1 & 0xff;
               bitCount = bitCount + 1;
               if (7 < bitfieldValue) {
                 bitOffset = bitOffset + 1;
               }
               paletteIndexLow = 0;
               if (bitfieldValue < 8) {
                 paletteIndexLow = nextBitIndex + 1;
               }
               byteOffset = (ulong)(-(frameData[(bitfieldByteOffset & 0xff) + paletteIndex + paletteDataOffset] >> (ulong)(nextBitIndex & 0x1f)
                                 & 1) & 1 << (ulong)paletteIndexUint | (uint)byteOffset);
               nextBitIndex = paletteIndexLow;
             } while (bitIndex != bitCount);
           }
           if (frameData[paletteDataOffset] <= (byte)byteOffset) {
             puts("divoom_multipic_undecode: it err index!");
           }
           bitsPerIndex = frameData[paletteDataOffset + 1 + (byteOffset & 0xff)];
           goto LAB_0024b750;
         }
         if (bitIndex != 0) {
           bitCount = 0;
           nextBitIndex = 0;
           bitOffset = bitCursor * bitIndex >> 3;
           bitfieldValue = bitCursor * bitIndex & 7;
           do {
             byteOffset = (ulong)bitOffset;
             paletteIndexUint = bitCount & 0x1f;
             paletteIndexLow = bitfieldValue + 1 & 0xff;
             bitCount = bitCount + 1;
             if (7 < paletteIndexLow) {
               bitOffset = bitOffset + 1;
             }
             paletteEntryLow = 0;
             if (paletteIndexLow < 8) {
               paletteEntryLow = bitfieldValue + 1;
             }
             nextBitIndex = -(frameData[(byteOffset & 0xff) + paletteDataOffset] >> (ulong)(bitfieldValue & 0x1f) & 1) &
                      1 << (ulong)paletteIndexUint | nextBitIndex;
             bitfieldValue = paletteEntryLow;
           } while (bitIndex != bitCount);
           byteOffset = (ulong)((nextBitIndex >> 1 & 0x7f) + (nextBitIndex & 0xff));
           bitsPerIndex = paletteData[byteOffset];
           if ((nextBitIndex & 1) == 0) goto LAB_0024b708;
           paletteEntryLow = paletteData[byteOffset + 1];
           bitCount = (uint)(bitsPerIndex >> 4);
           goto LAB_0024b780;
         }
         byteOffset = 0;
         bitsPerIndex = *paletteData;
 LAB_0024b708:
         bitCount = bitsPerIndex & 0xf;
         bitOffset = (uint)(bitsPerIndex >> 4);
         paletteEntryLow = paletteData[byteOffset + 1] & 0xf;
       }
       byteOffset = (ulong)(bitCursor >> 1) + (ulong)bitCursor;
       if ((bitCursor & 1) == 0) {
         pixelBufferOffset = pixelBuffer + (byteOffset & 0xffffffff);
         *(byte *)(pixelBuffer + byteOffset) = (byte)bitCount | (byte)(bitOffset << 4);
         *(byte *)(pixelBufferOffset + 1) = *(byte *)(pixelBufferOffset + 1) & 0xf0 | paletteEntryLow;
       }
       else {
         *(byte *)(pixelBuffer + byteOffset) = *(byte *)(pixelBuffer + byteOffset) & 0xf | (byte)(bitCount << 4);
         *(byte *)(pixelBuffer + (byteOffset & 0xffffffff) + 1) = (byte)bitOffset | paletteEntryLow << 4;
       }
       bitCursor = bitCursor + 1;
     } while (bitCursor != 0x79);
     decodeResult = 1;
   }
   else {
     decodeResult = 0;
   }
   return decodeResult;
 }
 
 
 uint divoom_multipic_deocde_one(byte paletteSize1,byte paletteSize2,byte *paletteData,long pixelBuffer,byte *outputBuffer)
 
 {
   bool continueLoop;
   uint bitIndex;
   uint nextBitIndex;
   uint byteIndex;
   byte bitMask;
   uint bitsPerIndex1;
   uint paletteSize1Uint;
   ulong colorIndex;
   byte bitsPerIndex2;
   uint bitIndexCounter;
   uint bitOffset;
   ulong byteOffset;
   long pixelIndex;
   uint bitsPerIndex1Uint;
   ulong bitfieldByteOffset;
   byte currentByte;
   long outputOffset;
   
   paletteSize1Uint = (uint)paletteSize1;
   colorIndex = (ulong)paletteSize1Uint;
   if (paletteSize1Uint == 1) {
     outputBuffer[0] = 3;
     outputBuffer[1] = 1;
     outputBuffer[2] = *paletteData;
     paletteSize1Uint = 3;
     goto LAB_0024b10c;
   }
   bitsPerIndex1 = (uint)paletteSize2;
   if (paletteSize1Uint == 0) {
     bitsPerIndex2 = 0xff;
     if (bitsPerIndex1 != 0) goto LAB_0024aef0;
 LAB_0024af34:
     bitsPerIndex1Uint = 0xff;
   }
   else {
     bitsPerIndex2 = 0xff;
     bitIndexCounter = paletteSize1Uint;
     bitsPerIndex1 = 0;
     do {
       bitMask = bitsPerIndex1 + 1;
       if (bitsPerIndex2 != 0xff) {
         bitsPerIndex1 = bitsPerIndex1 + 1;
       }
       if ((bitIndexCounter & 1) != 0) {
         bitsPerIndex2 = bitsPerIndex1;
       }
       continueLoop = 1 < bitIndexCounter;
       bitIndexCounter = bitIndexCounter >> 1;
       bitsPerIndex1 = bitMask;
     } while (continueLoop);
     if (bitsPerIndex1 == 0) goto LAB_0024af34;
 LAB_0024aef0:
     bitsPerIndex1Uint = 0xff;
     bitIndexCounter = 0;
     do {
       nextBitIndex = bitIndexCounter + 1;
       if (((bitsPerIndex1Uint ^ 0xffffffff) & 0xff) != 0) {
         bitIndexCounter = bitIndexCounter + 1;
       }
       if ((bitsPerIndex1 & 1) != 0) {
         bitsPerIndex1Uint = bitIndexCounter;
       }
       continueLoop = 1 < bitsPerIndex1;
       bitIndexCounter = nextBitIndex;
       bitsPerIndex1 = bitsPerIndex1 >> 1;
     } while (continueLoop);
   }
   if (((uint)bitsPerIndex2 == (bitsPerIndex1Uint & 0xff)) ||
      ((bitsPerIndex1Uint & 0xff) * 0x79 + 7 >> 3 < paletteSize1Uint + ((uint)bitsPerIndex2 * 0x79 + 7 >> 3))) {
     paletteSize1Uint = bitsPerIndex1Uint & 0xff;
     if (paletteSize1Uint == 8) {
       bitsPerIndex1 = 0;
       bitIndexCounter = 8;
     }
     else {
       bitsPerIndex1 = (paletteSize1Uint * 0x79 + 7 >> 3) + 2;
       bitIndexCounter = paletteSize1Uint;
     }
     pixelIndex = 0;
     *outputBuffer = (byte)bitsPerIndex1;
     outputBuffer[1] = paletteSize2;
     do {
       if ((bitsPerIndex1Uint & 0xff) != 0) {
         byteIndex = bitIndexCounter * (int)pixelIndex;
         currentByte = *(byte *)(pixelBuffer + pixelIndex);
         bitIndex = 0;
         byteOffset = byteIndex >> 3 & 0x1fff;
         byteIndex = byteIndex & 7;
         do {
           bitfieldByteOffset = (ulong)byteOffset;
           nextBitIndex = bitIndex & 0x1f;
           bitOffset = byteIndex + 1 & 0xff;
           bitIndex = bitIndex + 1;
           bitMask = (byte)(1 << (ulong)(byteIndex & 0x1f));
           currentByte = outputBuffer[(bitfieldByteOffset & 0xff) + 2] & (bitMask ^ 0xff);
           if ((currentByte >> (ulong)nextBitIndex & 1) != 0) {
             currentByte = outputBuffer[(bitfieldByteOffset & 0xff) + 2] | bitMask;
           }
           if (7 < bitOffset) {
             byteOffset = byteOffset + 1;
           }
           nextBitIndex = 0;
           if (bitOffset < 8) {
             nextBitIndex = byteIndex + 1;
           }
           outputBuffer[(bitfieldByteOffset & 0xff) + 2] = currentByte;
           byteIndex = nextBitIndex;
         } while (paletteSize1Uint != bitIndex);
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     paletteSize1Uint = 0x7b;
     if ((bitsPerIndex1 & 0xff) != 0) {
       paletteSize1Uint = bitsPerIndex1;
     }
   }
   else {
     outputOffset = colorIndex + 2;
     outputBuffer[1] = paletteSize1;
     *outputBuffer = (char)outputOffset + (char)((uint)bitsPerIndex2 * 0x79 + 7 >> 3);
     memcpy(outputBuffer + 2,paletteData,colorIndex);
     pixelIndex = 0;
     do {
       if (paletteSize1Uint != 0) {
         colorIndex = 0;
         do {
           if (paletteData[colorIndex] == *(byte *)(pixelBuffer + pixelIndex)) goto LAB_0024b0a8;
           colorIndex = colorIndex + 1;
         } while (colorIndex != paletteSize1Uint);
       }
       puts("divoom_multipic_get_color_index: it is err and pls check it!");
       colorIndex = (ulong)paletteSize1Uint;
 LAB_0024b0a8:
       if (bitsPerIndex2 != 0) {
         bitIndex = 0;
         bitfieldByteOffset = pixelIndex * (ulong)bitsPerIndex2 >> 3;
         byteIndex = (uint)(pixelIndex * (ulong)bitsPerIndex2) & 7;
         do {
           byteOffset = bitfieldByteOffset & 0xff;
           nextBitIndex = bitIndex & 0x1f;
           bitOffset = byteIndex + 1 & 0xff;
           bitIndex = bitIndex + 1;
           bitMask = (byte)(1 << (ulong)(byteIndex & 0x1f));
           currentByte = outputBuffer[byteOffset + outputOffset] & (bitMask ^ 0xff);
           if (((uint)colorIndex >> (ulong)nextBitIndex & 1) != 0) {
             currentByte = outputBuffer[byteOffset + outputOffset] | bitMask;
           }
           nextBitIndex = (uint)bitfieldByteOffset;
           if (7 < bitOffset) {
             nextBitIndex = nextBitIndex + 1;
           }
           bitfieldByteOffset = (ulong)nextBitIndex;
           nextBitIndex = 0;
           if (bitOffset < 8) {
             nextBitIndex = byteIndex + 1;
           }
           outputBuffer[byteOffset + outputOffset] = currentByte;
           byteIndex = nextBitIndex;
         } while (bitsPerIndex2 != bitIndex);
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     paletteSize1Uint = (uint)*outputBuffer;
   }
 LAB_0024b10c:
   return paletteSize1Uint & 0xff;
 }
 
 
 byte * divoom_multipic_encode(long inputImages,byte imageCount,undefined2 *outputSize)
 
 {
   long pixelOffset;
   uint paletteSize;
   long stackCanaryPtr;
   byte rgbByte1;
   int encodedSize;
   byte *outputBuffer;
   void *colorUsageMap;
   void *colorMapping;
   ulong paletteIndex;
   ulong pixelIndex;
   ulong colorIndex;
   undefined1 *pixelDataPtr;
   byte *palettePtr;
   void *frameColorMap;
   ushort colorsUsed;
   ulong byteOffset;
   long frameOffset;
   ulong frameIndex;
   byte rgbByte2;
   byte rgbByte3;
   undefined8 *paletteSizePtr;
   size_t mapSize;
   ulong totalPaletteSize;
   undefined2 finalSize;
   int currentEncodedSize;
   byte paletteBuffer [364];
   undefined1 pixelIndices [1452];
   undefined8 local_80;
   undefined4 local_78;
   long stackCanary;
   
   stackCanaryPtr = tpidr_el0;
   stackCanary = *(long *)(stackCanaryPtr + 0x28);
   memset(pixelIndices,0,0x5ac);
   outputBuffer = (byte *)malloc(0x2800);
   if (imageCount == 0) {
     totalPaletteSize = 0;
   }
   else {
     frameIndex = 0;
     totalPaletteSize = 0;
     do {
       frameOffset = inputImages + frameIndex * 0xb6;
       pixelIndex = 0;
       colorIndex = totalPaletteSize;
       do {
         pixelOffset = (pixelIndex >> 1 & 0x7fff) + pixelIndex;
         rgbByte2 = *(byte *)(frameOffset + pixelOffset);
         pixelOffset = pixelOffset + frameOffset;
         if ((pixelIndex & 1) == 0) {
           rgbByte3 = rgbByte2 & 0xf;
           rgbByte2 = rgbByte2 >> 4;
           rgbByte1 = *(byte *)(pixelOffset + 1) & 0xf;
           if ((colorIndex & 0xffff) == 0) goto LAB_0024b284;
 LAB_0024b228:
           totalPaletteSize = colorIndex & 0xffff;
           paletteIndex = 0;
           palettePtr = (byte *)((ulong)paletteBuffer | 2);
           do {
             if (((palettePtr[-2] == rgbByte3) && (palettePtr[-1] == rgbByte2)) && (*palettePtr == rgbByte1))
             goto code_r0x0024b1e8;
             paletteIndex = paletteIndex + 1;
             palettePtr = palettePtr + 3;
           } while (totalPaletteSize != paletteIndex);
         }
         else {
           rgbByte1 = *(byte *)(pixelOffset + 1);
           rgbByte3 = rgbByte2 >> 4;
           rgbByte2 = rgbByte1 & 0xf;
           rgbByte1 = rgbByte1 >> 4;
           if ((colorIndex & 0xffff) != 0) goto LAB_0024b228;
 LAB_0024b284:
           totalPaletteSize = 0;
         }
         pixelOffset = totalPaletteSize * 3;
         paletteBuffer[pixelOffset] = rgbByte3;
         paletteBuffer[pixelOffset + 1] = rgbByte2;
         paletteBuffer[pixelOffset + 2] = rgbByte1;
         paletteIndex = totalPaletteSize;
         totalPaletteSize = (ulong)(((uint)colorIndex & 0xffff) + 1);
 code_r0x0024b1e8:
         pixelIndices[pixelIndex + frameIndex * 0x79] = (char)paletteIndex;
         pixelIndex = pixelIndex + 1;
         colorIndex = totalPaletteSize;
       } while (pixelIndex != 0x79);
       frameIndex = frameIndex + 1;
     } while (frameIndex != imageCount);
   }
   frameIndex = totalPaletteSize & 0xffff;
   mapSize = (frameIndex + (totalPaletteSize & 0xffff) * 2) * 4;
   colorUsageMap = malloc(mapSize);
   colorMapping = malloc(mapSize);
   local_80 = 0;
   local_78 = 0;
   memset(colorMapping,0,mapSize);
   memset(colorUsageMap,0,mapSize);
   paletteSize = (uint)totalPaletteSize & 0xffff;
   byteOffset = (ulong)paletteSize;
   if (imageCount == 0) {
     *outputBuffer = 0;
     outputBuffer[1] = (byte)frameIndex;
     colorIndex = frameIndex;
     if ((totalPaletteSize & 0xffff) == 0) {
       finalSize = 2;
       goto LAB_0024b4a0;
     }
 LAB_0024b414:
     totalPaletteSize = 0;
     palettePtr = (byte *)((ulong)paletteBuffer | 2);
     do {
       paletteIndex = totalPaletteSize >> 1 & 0x7fffffff;
       if ((totalPaletteSize & 1) == 0) {
         paletteIndex = totalPaletteSize + paletteIndex;
         byteOffset = (ulong)((int)paletteIndex + 1);
         outputBuffer[(paletteIndex & 0xffffffff) + 2] = palettePtr[-2] | palettePtr[-1] << 4;
         outputBuffer[byteOffset + 2] = *palettePtr | outputBuffer[byteOffset + 2] & 0xf0;
       }
       else {
         paletteIndex = totalPaletteSize + paletteIndex;
         byteOffset = paletteIndex & 0xffffffff;
         rgbByte3 = palettePtr[-1];
         rgbByte2 = *palettePtr;
         outputBuffer[byteOffset + 2] = outputBuffer[byteOffset + 2] & 0xf | palettePtr[-2] << 4;
         outputBuffer[(ulong)((int)paletteIndex + 1) + 2] = rgbByte3 | rgbByte2 << 4;
       }
       totalPaletteSize = totalPaletteSize + 1;
       palettePtr = palettePtr + 3;
     } while (frameIndex != totalPaletteSize);
   }
   else {
     colorIndex = 0;
     pixelDataPtr = pixelIndices;
     do {
       frameOffset = 0;
       do {
         palettePtr = pixelDataPtr + frameOffset;
         frameOffset = frameOffset + 1;
         *(undefined1 *)((long)colorUsageMap + (colorIndex & 0xffffffff) * frameIndex + (ulong)*palettePtr) = 1;
       } while (frameOffset != 0x79);
       colorIndex = colorIndex + 1;
       pixelDataPtr = pixelDataPtr + 0x79;
     } while (colorIndex != imageCount);
     if (imageCount != 0) {
       colorIndex = 0;
       frameColorMap = colorUsageMap;
       do {
         if ((totalPaletteSize & 0xffff) == 0) {
           colorsUsed = 0;
         }
         else {
           paletteIndex = 0;
           colorsUsed = 0;
           do {
             if (*(char *)((long)frameColorMap + paletteIndex) != '\0') {
               byteOffset = (ulong)colorsUsed;
               colorsUsed = colorsUsed + 1;
               *(char *)((long)colorMapping + colorIndex * frameIndex + byteOffset) = (char)paletteIndex;
             }
             paletteIndex = paletteIndex + 1;
           } while (frameIndex != paletteIndex);
         }
         *(char *)((long)&local_80 + colorIndex) = (char)colorsUsed;
         colorIndex = colorIndex + 1;
         frameColorMap = (void *)((long)frameColorMap + frameIndex);
       } while (colorIndex != imageCount);
     }
     *outputBuffer = imageCount;
     outputBuffer[1] = (byte)paletteSize;
     colorIndex = byteOffset;
     if ((int)frameIndex != 0) goto LAB_0024b414;
   }
   currentEncodedSize = (paletteSize * 3 + 1 >> 1) + 2;
   finalSize = (undefined2)currentEncodedSize;
   if (imageCount != 0) {
     totalPaletteSize = (ulong)imageCount;
     pixelDataPtr = pixelIndices;
     paletteSizePtr = &local_80;
     frameColorMap = colorMapping;
     do {
       encodedSize = divoom_multipic_deocde_one
                         (*(undefined1 *)paletteSizePtr,colorIndex,frameColorMap,pixelDataPtr,outputBuffer + (ushort)currentEncodedSize);
       pixelDataPtr = pixelDataPtr + 0x79;
       currentEncodedSize = encodedSize + currentEncodedSize;
       finalSize = (undefined2)currentEncodedSize;
       frameColorMap = (void *)((long)frameColorMap + byteOffset);
       totalPaletteSize = totalPaletteSize - 1;
       paletteSizePtr = (undefined8 *)((long)paletteSizePtr + 1);
     } while (totalPaletteSize != 0);
   }
 LAB_0024b4a0:
   free(colorMapping);
   free(colorUsageMap);
   if (outputSize != (undefined2 *)0x0) {
     *outputSize = finalSize;
   }
   if (*(long *)(stackCanaryPtr + 0x28) != stackCanary) {
                     /* WARNING: Subroutine does not return */
     __stack_chk_fail();
   }
   return outputBuffer;
 }
 
 
 uint divoom_multipic_get_bits(byte value)
 
 {
   bool continueLoop;
   uint nextBitCount;
   uint bitsNeeded;
   uint remainingValue;
   uint bitCount;
   
   if (value != 0) {
     bitsNeeded = 0xff;
     remainingValue = (uint)value;
     bitCount = 0;
     do {
       nextBitCount = bitCount + 1;
       if (((bitsNeeded ^ 0xffffffff) & 0xff) != 0) {
         bitCount = bitCount + 1;
       }
       if ((remainingValue & 1) != 0) {
         bitsNeeded = bitCount;
       }
       continueLoop = 1 < remainingValue;
       remainingValue = remainingValue >> 1;
       bitCount = nextBitCount;
     } while (continueLoop);
     return bitsNeeded;
   }
   return 0xff;
 }
 
 
 ulong divoom_multipic_get_color_index(long paletteData,uint paletteSize,char targetColor)
 
 {
   ulong index;
   
   if ((paletteSize & 0xff) != 0) {
     index = 0;
     do {
       if (*(char *)(paletteData + index) == targetColor) {
         return index & 0xffffffff;
       }
       index = index + 1;
     } while (((ulong)paletteSize & 0xff) != index);
   }
   puts("divoom_multipic_get_color_index: it is err and pls check it!");
   return (ulong)paletteSize;
 }
 
 
 void divoom_multipic_get_data(long packedData,uint index,byte *rgbOutput)
 
 {
   ulong byteOffset;
   
   byteOffset = (ulong)(index + ((index & 0xfffe) >> 1)) & 0xffff;
   if ((index & 1) == 0) {
     *rgbOutput = *(byte *)(packedData + byteOffset) & 0xf;
     rgbOutput[1] = *(byte *)(packedData + byteOffset) >> 4;
     rgbOutput[2] = ((byte *)(packedData + byteOffset))[1] & 0xf;
     return;
   }
   *rgbOutput = *(byte *)(packedData + byteOffset) >> 4;
   rgbOutput[1] = *(byte *)(byteOffset + packedData + 1) & 0xf;
   rgbOutput[2] = *(byte *)(byteOffset + packedData + 1) >> 4;
   return;
 }
 
 
 bool divoom_multipic_get_deocde_type(byte paletteSize1,uint bitsPerIndex1,byte bitsPerIndex2)
 
 {
   if ((bitsPerIndex1 & 0xff) == (uint)bitsPerIndex2) {
     return false;
   }
   return ((bitsPerIndex1 & 0xff) * 0x79 + 7 >> 3) + (uint)paletteSize1 <= (uint)bitsPerIndex2 * 0x79 + 7 >> 3;
 }
 
 
 uint divoom_multipic_get_dot_info(long bitstreamBuffer,int pixelIndex,uint bitsPerIndex)
 
 {
   uint nextBitOffset;
   uint newBitOffset;
   uint bitIndex;
   uint byteIndex;
   uint resultValue;
   uint bitCounter;
   uint totalBitOffset;
   ulong byteOffset;
   
   if ((bitsPerIndex & 0xff) != 0) {
     totalBitOffset = (bitsPerIndex & 0xff) * pixelIndex;
     bitCounter = 0;
     resultValue = 0;
     byteIndex = totalBitOffset >> 3 & 0x1fff;
     totalBitOffset = totalBitOffset & 7;
     do {
       byteOffset = (ulong)byteIndex;
       bitIndex = bitCounter & 0x1f;
       nextBitOffset = totalBitOffset + 1 & 0xff;
       bitCounter = bitCounter + 1;
       if (7 < nextBitOffset) {
         byteIndex = byteIndex + 1;
       }
       newBitOffset = 0;
       if (nextBitOffset < 8) {
         newBitOffset = totalBitOffset + 1;
       }
       resultValue = -(*(byte *)(bitstreamBuffer + (byteOffset & 0xff)) >> (ulong)(totalBitOffset & 0x1f) & 1) &
               1 << (ulong)bitIndex | resultValue;
       totalBitOffset = newBitOffset;
     } while ((bitsPerIndex & 0xff) != bitCounter);
     return resultValue;
   }
   return 0;
 }
 
 
 void divoom_multipic_set_data(uint index,byte *rgbInput,long packedData)
 
 {
   byte *targetByte;
   byte savedByte;
   
   targetByte = (byte *)(packedData + (ulong)((index & 0xffff) >> 1) + (ulong)(index & 0xffff));
   if ((index & 1) == 0) {
     savedByte = targetByte[1];
     *targetByte = *rgbInput | rgbInput[1] << 4;
     targetByte[1] = savedByte & 0xf0;
     targetByte[1] = rgbInput[2] | savedByte & 0xf0;
     return;
   }
   savedByte = *targetByte;
   *targetByte = savedByte & 0xf;
   *targetByte = savedByte & 0xf | *rgbInput << 4;
   targetByte[1] = rgbInput[1] | rgbInput[2] << 4;
   return;
 }
 
 
 void divoom_multipic_set_dot_info(long bitstreamBuffer,int pixelIndex,uint bitsPerIndex,uint valueToWrite)
 
 {
   uint nextBitOffset;
   byte currentByte;
   byte savedByte;
   uint bitIndex;
   uint byteIndex;
   byte bitMask;
   uint bitCounter;
   uint totalBitOffset;
   ulong byteOffset;
   
   if ((bitsPerIndex & 0xff) != 0) {
     totalBitOffset = (bitsPerIndex & 0xff) * pixelIndex;
     bitCounter = 0;
     byteIndex = totalBitOffset >> 3 & 0x1fff;
     totalBitOffset = totalBitOffset & 7;
     do {
       byteOffset = (ulong)byteIndex;
       bitIndex = bitCounter & 0x1f;
       nextBitOffset = totalBitOffset + 1 & 0xff;
       savedByte = *(byte *)(bitstreamBuffer + (byteOffset & 0xff));
       bitCounter = bitCounter + 1;
       bitMask = (byte)(1 << (ulong)(totalBitOffset & 0x1f));
       currentByte = savedByte & (bitMask ^ 0xff);
       if (((valueToWrite & 0xff) >> (ulong)bitIndex & 1) != 0) {
         currentByte = savedByte | bitMask;
       }
       if (7 < nextBitOffset) {
         byteIndex = byteIndex + 1;
       }
       bitIndex = 0;
       if (nextBitOffset < 8) {
         bitIndex = totalBitOffset + 1;
       }
       *(byte *)(bitstreamBuffer + (byteOffset & 0xff)) = currentByte;
       totalBitOffset = bitIndex;
     } while ((bitsPerIndex & 0xff) != bitCounter);
   }
   return;
 }
 
 
 void divoom_pic_decode(long outputBuffer,undefined1 *encodedData)
 
 {
   ulong pixelOffset;
   byte paletteSize;
   undefined1 decodeMode;
   uint byteOffset;
   long stackCanaryPtr;
   long paletteIndex;
   ulong paletteColorIndex;
   ushort pixelIndex;
   ushort currentPixelIndex;
   uint runLength;
   byte *targetByte;
   byte rgbByte1;
   ulong nextByteOffset;
   byte rgbByte2;
   ulong packedDataOffset;
   byte rgbByte3;
   byte paletteBuffer [368];
   long stackCanary;
   
   stackCanaryPtr = tpidr_el0;
   stackCanary = *(long *)(stackCanaryPtr + 0x28);
   paletteSize = encodedData[1];
   decodeMode = *encodedData;
   if (paletteSize != 0) {
     paletteColorIndex = 0;
     targetByte = (byte *)((ulong)paletteBuffer | 2);
     do {
       packedDataOffset = (ulong)((uint)paletteColorIndex + (((uint)paletteColorIndex & 0xfffe) >> 1)) & 0xffff;
       rgbByte1 = encodedData[packedDataOffset + 2];
       if ((paletteColorIndex & 1) == 0) {
         rgbByte3 = rgbByte1 & 0xf;
         rgbByte1 = rgbByte1 >> 4;
         rgbByte2 = encodedData[packedDataOffset + 3] & 0xf;
       }
       else {
         rgbByte3 = rgbByte1 >> 4;
         rgbByte1 = encodedData[packedDataOffset + 3] & 0xf;
         rgbByte2 = (byte)encodedData[packedDataOffset + 3] >> 4;
       }
       paletteColorIndex = paletteColorIndex + 1;
       targetByte[-2] = rgbByte3;
       targetByte[-1] = rgbByte1;
       *targetByte = rgbByte2;
       targetByte = targetByte + 3;
     } while (paletteSize != paletteColorIndex);
   }
   paletteColorIndex = ((ulong)paletteSize * 3 + 1 >> 1) + 2;
   switch(decodeMode) {
   case 0:
     pixelIndex = 0;
     do {
       paletteSize = encodedData[paletteColorIndex & 0xffff];
       if (0xf < paletteSize) {
         paletteIndex = ((ulong)paletteSize & 0xf) * 3;
         runLength = (uint)(paletteSize >> 4);
         if (paletteSize >> 4 < 2) {
           runLength = 1;
         }
         currentPixelIndex = pixelIndex;
         do {
           targetByte = (byte *)(outputBuffer + (ulong)(currentPixelIndex >> 1) + (ulong)currentPixelIndex);
           if ((currentPixelIndex & 1) == 0) {
             rgbByte1 = paletteBuffer[paletteIndex + 2];
             *targetByte = paletteBuffer[paletteIndex] | paletteBuffer[paletteIndex + 1] << 4;
             targetByte[1] = rgbByte1 | targetByte[1] & 0xf0;
           }
           else {
             rgbByte1 = paletteBuffer[paletteIndex + 1];
             rgbByte3 = paletteBuffer[paletteIndex + 2];
             *targetByte = *targetByte & 0xf | paletteBuffer[paletteIndex] << 4;
             targetByte[1] = rgbByte1 | rgbByte3 << 4;
           }
           currentPixelIndex = currentPixelIndex + 1;
           runLength = runLength - 1;
         } while (runLength != 0);
       }
       paletteColorIndex = (ulong)((int)paletteColorIndex + 1);
       pixelIndex = pixelIndex + (paletteSize >> 4);
     } while (pixelIndex < 0x79);
     break;
   case 1:
     pixelIndex = 0;
     do {
       byteOffset = pixelIndex + (pixelIndex >> 1);
       if ((pixelIndex & 1) == 0) {
         paletteIndex = ((ulong)(byte)encodedData[(pixelIndex >> 1) + paletteColorIndex] & 0xf) * 3;
         paletteSize = paletteBuffer[paletteIndex + 2];
         *(byte *)(outputBuffer + (ulong)byteOffset) = paletteBuffer[paletteIndex] | paletteBuffer[paletteIndex + 1] << 4;
         *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) =
              paletteSize | *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) & 0xf0;
       }
       else {
         paletteIndex = (ulong)((byte)encodedData[(pixelIndex >> 1) + paletteColorIndex] >> 4) * 3;
         paletteSize = paletteBuffer[paletteIndex + 1];
         rgbByte1 = paletteBuffer[paletteIndex + 2];
         *(byte *)(outputBuffer + (ulong)byteOffset) =
              *(byte *)(outputBuffer + (ulong)byteOffset) & 0xf | paletteBuffer[paletteIndex] << 4;
         *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) = paletteSize | rgbByte1 << 4;
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     break;
   case 2:
     pixelIndex = 0;
     do {
       paletteSize = encodedData[(ulong)((int)paletteColorIndex + 1) & 0xffff];
       runLength = (uint)paletteSize;
       if (runLength != 0) {
         paletteIndex = (ulong)(byte)encodedData[paletteColorIndex & 0xffff] * 3;
         currentPixelIndex = pixelIndex;
         do {
           targetByte = (byte *)(outputBuffer + (ulong)(currentPixelIndex >> 1) + (ulong)currentPixelIndex);
           if ((currentPixelIndex & 1) == 0) {
             rgbByte1 = paletteBuffer[paletteIndex + 2];
             *targetByte = paletteBuffer[paletteIndex] | paletteBuffer[paletteIndex + 1] << 4;
             targetByte[1] = rgbByte1 | targetByte[1] & 0xf0;
           }
           else {
             rgbByte1 = paletteBuffer[paletteIndex + 1];
             rgbByte3 = paletteBuffer[paletteIndex + 2];
             *targetByte = *targetByte & 0xf | paletteBuffer[paletteIndex] << 4;
             targetByte[1] = rgbByte1 | rgbByte3 << 4;
           }
           currentPixelIndex = currentPixelIndex + 1;
           runLength = runLength - 1;
         } while (runLength != 0);
       }
       pixelIndex = pixelIndex + paletteSize;
       paletteColorIndex = (ulong)((int)paletteColorIndex + 2);
     } while (pixelIndex < 0x79);
     break;
   default:
     pixelIndex = 0;
     do {
       paletteIndex = (ulong)(byte)encodedData[pixelIndex + paletteColorIndex] * 3;
       if ((pixelIndex & 1) == 0) {
         pixelOffset = pixelIndex + (pixelIndex >> 1);
         paletteSize = paletteBuffer[paletteIndex + 2];
         nextByteOffset = (ulong)((int)pixelOffset + 1);
         *(byte *)(outputBuffer + (pixelOffset & 0xffffffff)) = paletteBuffer[paletteIndex] | paletteBuffer[paletteIndex + 1] << 4;
         *(byte *)(outputBuffer + nextByteOffset) = paletteSize | *(byte *)(outputBuffer + nextByteOffset) & 0xf0;
       }
       else {
         pixelOffset = pixelIndex + (pixelIndex >> 1);
         nextByteOffset = pixelOffset & 0xffffffff;
         paletteSize = paletteBuffer[paletteIndex + 1];
         rgbByte1 = paletteBuffer[paletteIndex + 2];
         *(byte *)(outputBuffer + nextByteOffset) = *(byte *)(outputBuffer + nextByteOffset) & 0xf | paletteBuffer[paletteIndex] << 4;
         *(byte *)(outputBuffer + (ulong)((int)pixelOffset + 1)) = paletteSize | rgbByte1 << 4;
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     break;
   case 4:
     pixelIndex = 0;
     do {
       byteOffset = pixelIndex + (pixelIndex >> 1);
       paletteColorIndex = (ulong)byteOffset;
       if ((pixelIndex & 1) == 0) {
         *(byte *)(outputBuffer + paletteColorIndex) = paletteBuffer[0] | paletteBuffer[1] << 4;
         *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) =
              paletteBuffer[2] | *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) & 0xf0;
       }
       else {
         *(byte *)(outputBuffer + paletteColorIndex) = paletteBuffer[0] << 4 | *(byte *)(outputBuffer + paletteColorIndex) & 0xf;
         *(byte *)(outputBuffer + (ulong)(byteOffset + 1)) = paletteBuffer[1] | paletteBuffer[2] << 4;
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     break;
   case 5:
     pixelIndex = 0;
     do {
       byteOffset = pixelIndex >> 1;
       packedDataOffset = (ulong)(pixelIndex + byteOffset);
       if (((byte)encodedData[(pixelIndex >> 3) + paletteColorIndex] >> (ulong)(pixelIndex & 7) & 1) == 0) {
         if ((pixelIndex & 1) == 0) {
           *(byte *)(outputBuffer + packedDataOffset) = paletteBuffer[0] | paletteBuffer[1] << 4;
           packedDataOffset = (ulong)(pixelIndex + byteOffset + 1);
           paletteSize = paletteBuffer[2] | *(byte *)(outputBuffer + packedDataOffset) & 0xf0;
           goto LAB_0024ac54;
         }
         *(byte *)(outputBuffer + packedDataOffset) = paletteBuffer[0] << 4 | *(byte *)(outputBuffer + packedDataOffset) & 0xf;
         *(byte *)(outputBuffer + (ulong)(pixelIndex + byteOffset + 1)) = paletteBuffer[1] | paletteBuffer[2] << 4;
       }
       else if ((pixelIndex & 1) == 0) {
         *(byte *)(outputBuffer + packedDataOffset) = paletteBuffer[3] | paletteBuffer[4] << 4;
         packedDataOffset = (ulong)(pixelIndex + byteOffset + 1);
         paletteSize = paletteBuffer[5] | *(byte *)(outputBuffer + packedDataOffset) & 0xf0;
 LAB_0024ac54:
         *(byte *)(outputBuffer + packedDataOffset) = paletteSize;
       }
       else {
         *(byte *)(outputBuffer + packedDataOffset) = paletteBuffer[3] << 4 | *(byte *)(outputBuffer + packedDataOffset) & 0xf;
         *(byte *)(outputBuffer + (ulong)(pixelIndex + byteOffset + 1)) = paletteBuffer[4] | paletteBuffer[5] << 4;
       }
       pixelIndex = pixelIndex + 1;
     } while (pixelIndex != 0x79);
     break;
   }
   if (*(long *)(stackCanaryPtr + 0x28) == stackCanary) {
     return;
   }
                     /* WARNING: Subroutine does not return */
   __stack_chk_fail();
 }
 
 
 undefined1 * divoom_pic_encode(long inputImage,short *outputSize)
 
 {
   ushort outputOffset;
   undefined8 *outputPtr;
   short sizeValue;
   long stackCanaryPtr;
   undefined1 *encodedData;
   undefined1 encodeMode;
   ushort dataOffset;
   ulong pixelIndex;
   ulong paletteSize;
   byte rgbByte1;
   uint paletteOffset;
   byte *palettePtr;
   byte rgbByte2;
   byte rgbByte3;
   uint runLength;
   ulong byteOffset;
   long paletteIndexLong;
   char runLengthChar;
   ulong paletteIndexUlong;
   ulong colorIndex;
   uint totalPaletteSize;
   byte pixelColorIndices [121];
   char local_1cb;
   byte paletteBuffer [368];
   long stackCanary;
   
   stackCanaryPtr = tpidr_el0;
   pixelIndex = 0;
   stackCanary = *(long *)(stackCanaryPtr + 0x28);
   paletteSize = 0;
   do {
     paletteIndexLong = (pixelIndex >> 1 & 0x7fff) + pixelIndex;
     rgbByte2 = *(byte *)(inputImage + paletteIndexLong);
     paletteIndexLong = paletteIndexLong + inputImage;
     if ((pixelIndex & 1) == 0) {
       rgbByte1 = rgbByte2 & 0xf;
       rgbByte2 = rgbByte2 >> 4;
       rgbByte3 = *(byte *)(paletteIndexLong + 1) & 0xf;
       if ((paletteSize & 0xffff) == 0) goto LAB_0024a3ac;
 LAB_0024a350:
       colorIndex = paletteSize & 0xffff;
       paletteIndexUlong = 0;
       palettePtr = (byte *)((ulong)paletteBuffer | 2);
       do {
         if (((palettePtr[-2] == rgbByte1) && (palettePtr[-1] == rgbByte2)) && (*palettePtr == rgbByte3))
         goto LAB_0024a314;
         paletteIndexUlong = paletteIndexUlong + 1;
         palettePtr = palettePtr + 3;
       } while (colorIndex != paletteIndexUlong);
     }
     else {
       rgbByte3 = *(byte *)(paletteIndexLong + 1);
       rgbByte1 = rgbByte2 >> 4;
       rgbByte2 = rgbByte3 & 0xf;
       rgbByte3 = rgbByte3 >> 4;
       if ((paletteSize & 0xffff) != 0) goto LAB_0024a350;
 LAB_0024a3ac:
       colorIndex = 0;
     }
     paletteIndexLong = colorIndex * 3;
     paletteBuffer[paletteIndexLong] = rgbByte1;
     paletteBuffer[paletteIndexLong + 1] = rgbByte2;
     paletteBuffer[paletteIndexLong + 2] = rgbByte3;
     paletteIndexUlong = colorIndex;
     colorIndex = (ulong)(((uint)paletteSize & 0xffff) + 1);
 LAB_0024a314:
     pixelColorIndices[pixelIndex] = (byte)paletteIndexUlong;
     pixelIndex = pixelIndex + 1;
     paletteSize = colorIndex;
   } while (pixelIndex != 0x79);
   totalPaletteSize = (uint)colorIndex;
   paletteOffset = totalPaletteSize & 0xffff;
   printf("divoom_pic_decode: color num: %d\n",(ulong)paletteOffset);
   paletteOffset = (paletteOffset + (uint)(ushort)colorIndex * 2 + 1 >> 1) + 2;
   pixelIndex = (ulong)paletteOffset & 0xffff;
   sizeValue = (short)paletteOffset;
   *outputSize = sizeValue;
   encodedData = (undefined1 *)malloc(pixelIndex + 0x16b);
   memset(encodedData,0,pixelIndex + 0x16b);
   if (paletteOffset == 1) {
     encodeMode = 4;
 LAB_0024a440:
     *encodedData = encodeMode;
     encodedData[1] = (char)colorIndex;
 LAB_0024a448:
     paletteSize = 0;
     palettePtr = (byte *)((ulong)paletteBuffer | 2);
     do {
       paletteIndexUlong = paletteSize >> 1 & 0x7fffffff;
       if ((paletteSize & 1) == 0) {
         paletteIndexUlong = paletteSize + paletteIndexUlong;
         byteOffset = (ulong)((int)paletteIndexUlong + 1);
         encodedData[(paletteIndexUlong & 0xffffffff) + 2] = palettePtr[-2] | palettePtr[-1] << 4;
         encodedData[byteOffset + 2] = *palettePtr | encodedData[byteOffset + 2] & 0xf0;
       }
       else {
         paletteIndexUlong = paletteSize + paletteIndexUlong;
         byteOffset = paletteIndexUlong & 0xffffffff;
         rgbByte1 = palettePtr[-1];
         rgbByte2 = *palettePtr;
         encodedData[byteOffset + 2] = encodedData[byteOffset + 2] & 0xf | palettePtr[-2] << 4;
         encodedData[(ulong)((int)paletteIndexUlong + 1) + 2] = rgbByte1 | rgbByte2 << 4;
       }
       paletteSize = paletteSize + 1;
       palettePtr = palettePtr + 3;
     } while ((colorIndex & 0xffff) != paletteSize);
     if ((totalPaletteSize & 0xffff) == 1) {
       dataOffset = 0;
       goto LAB_0024a780;
     }
     if ((totalPaletteSize & 0xffff) == 2) {
       paletteSize = 0;
       do {
         palettePtr = pixelColorIndices + paletteSize;
         paletteIndexLong = (paletteSize >> 3 & 0x1fff) + pixelIndex;
         paletteIndexUlong = paletteSize & 7;
         paletteSize = paletteSize + 1;
         encodedData[paletteIndexLong] = encodedData[paletteIndexLong] | *palettePtr << paletteIndexUlong;
       } while (paletteSize != 0x79);
       dataOffset = 0x10;
       goto LAB_0024a780;
     }
     if ((totalPaletteSize & 0xffff) < 0x11) goto LAB_0024a540;
     paletteSize = 0;
     dataOffset = 0;
     do {
       runLength = (uint)paletteSize;
       palettePtr = pixelColorIndices + paletteSize;
       if (runLength < 0x78) {
         runLength = 0x77 - runLength;
         paletteIndexLong = 0;
         if (0xc < runLength) {
           runLength = 0xd;
         }
         do {
           if (*palettePtr != pixelColorIndices[paletteIndexLong + paletteSize + 1]) break;
           paletteIndexLong = paletteIndexLong + 1;
         } while ((ulong)(runLength + 2) - 1 != paletteIndexLong);
         runLength = runLength + (int)paletteIndexLong;
         runLengthChar = (char)paletteIndexLong + '\x01';
       }
       else {
         runLengthChar = '\x01';
       }
       outputOffset = dataOffset | 1;
       paletteIndexUlong = (ulong)dataOffset;
       runLength = runLength + 1 & 0xffff;
       paletteSize = (ulong)runLength;
       dataOffset = dataOffset + 2;
       encodedData[pixelIndex + paletteIndexUlong] = *palettePtr;
       encodedData[pixelIndex + outputOffset] = runLengthChar;
     } while (runLength < 0x79);
     if (dataOffset < 0x7a) goto LAB_0024a780;
     outputPtr = (undefined8 *)(encodedData + pixelIndex);
     dataOffset = 0x79;
     encodeMode = 3;
     outputPtr[9] = CONCAT17(pixelColorIndices[0x4f],
                          CONCAT16(pixelColorIndices[0x4e],
                                   CONCAT15(pixelColorIndices[0x4d],
                                            CONCAT14(pixelColorIndices[0x4c],
                                                     CONCAT13(pixelColorIndices[0x4b],
                                                              CONCAT12(pixelColorIndices[0x4a],
                                                                       CONCAT11(pixelColorIndices[0x49],
                                                                                pixelColorIndices[0x48]))))))
                         );
     outputPtr[8] = CONCAT17(pixelColorIndices[0x47],
                          CONCAT16(pixelColorIndices[0x46],
                                   CONCAT15(pixelColorIndices[0x45],
                                            CONCAT14(pixelColorIndices[0x44],
                                                     CONCAT13(pixelColorIndices[0x43],
                                                              CONCAT12(pixelColorIndices[0x42],
                                                                       CONCAT11(pixelColorIndices[0x41],
                                                                                pixelColorIndices[0x40]))))))
                         );
     outputPtr[0xb] = CONCAT17(pixelColorIndices[0x5f],
                            CONCAT16(pixelColorIndices[0x5e],
                                     CONCAT15(pixelColorIndices[0x5d],
                                              CONCAT14(pixelColorIndices[0x5c],
                                                       CONCAT13(pixelColorIndices[0x5b],
                                                                CONCAT12(pixelColorIndices[0x5a],
                                                                         CONCAT11(pixelColorIndices[0x59],
                                                                                  pixelColorIndices[0x58]))))
                                             )));
     outputPtr[10] = CONCAT17(pixelColorIndices[0x57],
                           CONCAT16(pixelColorIndices[0x56],
                                    CONCAT15(pixelColorIndices[0x55],
                                             CONCAT14(pixelColorIndices[0x54],
                                                      CONCAT13(pixelColorIndices[0x53],
                                                               CONCAT12(pixelColorIndices[0x52],
                                                                        CONCAT11(pixelColorIndices[0x51],
                                                                                 pixelColorIndices[0x50])))))
                                   ));
     outputPtr[0xd] = CONCAT17(pixelColorIndices[0x6f],
                            CONCAT16(pixelColorIndices[0x6e],
                                     CONCAT15(pixelColorIndices[0x6d],
                                              CONCAT14(pixelColorIndices[0x6c],
                                                       CONCAT13(pixelColorIndices[0x6b],
                                                                CONCAT12(pixelColorIndices[0x6a],
                                                                         CONCAT11(pixelColorIndices[0x69],
                                                                                  pixelColorIndices[0x68]))))
                                             )));
     outputPtr[0xc] = CONCAT17(pixelColorIndices[0x67],
                            CONCAT16(pixelColorIndices[0x66],
                                     CONCAT15(pixelColorIndices[0x65],
                                              CONCAT14(pixelColorIndices[100],
                                                       CONCAT13(pixelColorIndices[99],
                                                                CONCAT12(pixelColorIndices[0x62],
                                                                         CONCAT11(pixelColorIndices[0x61],
                                                                                  pixelColorIndices[0x60]))))
                                             )));
     *(ulong *)((long)outputPtr + 0x71) =
          CONCAT17(pixelColorIndices[0x78],
                   CONCAT16(pixelColorIndices[0x77],
                            CONCAT15(pixelColorIndices[0x76],
                                     CONCAT14(pixelColorIndices[0x75],
                                              CONCAT13(pixelColorIndices[0x74],
                                                       CONCAT12(pixelColorIndices[0x73],
                                                                CONCAT11(pixelColorIndices[0x72],
                                                                         pixelColorIndices[0x71])))))));
     *(ulong *)((long)outputPtr + 0x69) =
          CONCAT17(pixelColorIndices[0x70],
                   CONCAT16(pixelColorIndices[0x6f],
                            CONCAT15(pixelColorIndices[0x6e],
                                     CONCAT14(pixelColorIndices[0x6d],
                                              CONCAT13(pixelColorIndices[0x6c],
                                                       CONCAT12(pixelColorIndices[0x6b],
                                                                CONCAT11(pixelColorIndices[0x6a],
                                                                         pixelColorIndices[0x69])))))));
     outputPtr[1] = CONCAT17(pixelColorIndices[0xf],
                          CONCAT16(pixelColorIndices[0xe],
                                   CONCAT15(pixelColorIndices[0xd],
                                            CONCAT14(pixelColorIndices[0xc],
                                                     CONCAT13(pixelColorIndices[0xb],
                                                              CONCAT12(pixelColorIndices[10],
                                                                       CONCAT11(pixelColorIndices[9],
                                                                                pixelColorIndices[8])))))));
     *outputPtr = CONCAT17(pixelColorIndices[7],
                        CONCAT16(pixelColorIndices[6],
                                 CONCAT15(pixelColorIndices[5],
                                          CONCAT14(pixelColorIndices[4],
                                                   CONCAT13(pixelColorIndices[3],
                                                            CONCAT12(pixelColorIndices[2],
                                                                     CONCAT11(pixelColorIndices[1],
                                                                              pixelColorIndices[0])))))));
     outputPtr[3] = CONCAT17(pixelColorIndices[0x1f],
                          CONCAT16(pixelColorIndices[0x1e],
                                   CONCAT15(pixelColorIndices[0x1d],
                                            CONCAT14(pixelColorIndices[0x1c],
                                                     CONCAT13(pixelColorIndices[0x1b],
                                                              CONCAT12(pixelColorIndices[0x1a],
                                                                       CONCAT11(pixelColorIndices[0x19],
                                                                                pixelColorIndices[0x18]))))))
                         );
     outputPtr[2] = CONCAT17(pixelColorIndices[0x17],
                          CONCAT16(pixelColorIndices[0x16],
                                   CONCAT15(pixelColorIndices[0x15],
                                            CONCAT14(pixelColorIndices[0x14],
                                                     CONCAT13(pixelColorIndices[0x13],
                                                              CONCAT12(pixelColorIndices[0x12],
                                                                       CONCAT11(pixelColorIndices[0x11],
                                                                                pixelColorIndices[0x10]))))))
                         );
     outputPtr[5] = CONCAT17(pixelColorIndices[0x2f],
                          CONCAT16(pixelColorIndices[0x2e],
                                   CONCAT15(pixelColorIndices[0x2d],
                                            CONCAT14(pixelColorIndices[0x2c],
                                                     CONCAT13(pixelColorIndices[0x2b],
                                                              CONCAT12(pixelColorIndices[0x2a],
                                                                       CONCAT11(pixelColorIndices[0x29],
                                                                                pixelColorIndices[0x28]))))))
                         );
     outputPtr[4] = CONCAT17(pixelColorIndices[0x27],
                          CONCAT16(pixelColorIndices[0x26],
                                   CONCAT15(pixelColorIndices[0x25],
                                            CONCAT14(pixelColorIndices[0x24],
                                                     CONCAT13(pixelColorIndices[0x23],
                                                              CONCAT12(pixelColorIndices[0x22],
                                                                       CONCAT11(pixelColorIndices[0x21],
                                                                                pixelColorIndices[0x20]))))))
                         );
     outputPtr[7] = CONCAT17(pixelColorIndices[0x3f],
                          CONCAT16(pixelColorIndices[0x3e],
                                   CONCAT15(pixelColorIndices[0x3d],
                                            CONCAT14(pixelColorIndices[0x3c],
                                                     CONCAT13(pixelColorIndices[0x3b],
                                                              CONCAT12(pixelColorIndices[0x3a],
                                                                       CONCAT11(pixelColorIndices[0x39],
                                                                                pixelColorIndices[0x38]))))))
                         );
     outputPtr[6] = CONCAT17(pixelColorIndices[0x37],
                          CONCAT16(pixelColorIndices[0x36],
                                   CONCAT15(pixelColorIndices[0x35],
                                            CONCAT14(pixelColorIndices[0x34],
                                                     CONCAT13(pixelColorIndices[0x33],
                                                              CONCAT12(pixelColorIndices[0x32],
                                                                       CONCAT11(pixelColorIndices[0x31],
                                                                                pixelColorIndices[0x30]))))))
                         );
   }
   else {
     if (paletteOffset == 2) {
       encodeMode = 5;
       goto LAB_0024a440;
     }
     if (0x10 < (totalPaletteSize & 0xffff)) {
       encodeMode = 2;
       goto LAB_0024a440;
     }
     *encodedData = 0;
     encodedData[1] = (char)colorIndex;
     if ((colorIndex & 0xffff) != 0) goto LAB_0024a448;
 LAB_0024a540:
     paletteSize = 0;
     dataOffset = 0;
     do {
       runLength = (uint)paletteSize;
       palettePtr = pixelColorIndices + paletteSize;
       if (runLength < 0x78) {
         runLength = 0x77 - runLength;
         paletteIndexLong = 0;
         if (0xc < runLength) {
           runLength = 0xd;
         }
         do {
           if (*palettePtr != pixelColorIndices[paletteIndexLong + paletteSize + 1]) break;
           paletteIndexLong = paletteIndexLong + 1;
         } while ((ulong)(runLength + 2) - 1 != paletteIndexLong);
         runLength = runLength + (int)paletteIndexLong;
         paletteOffset = (int)paletteIndexLong + 1U & 0xff;
       }
       else {
         paletteOffset = 1;
       }
       paletteIndexUlong = (ulong)dataOffset;
       runLength = runLength + 1 & 0xffff;
       paletteSize = (ulong)runLength;
       dataOffset = dataOffset + 1;
       encodedData[pixelIndex + paletteIndexUlong] = *palettePtr | (byte)(paletteOffset << 4);
     } while (runLength < 0x79);
     if (dataOffset < 0xb7) goto LAB_0024a780;
     outputPtr = (undefined8 *)(encodedData + pixelIndex);
     outputPtr[5] = CONCAT17(pixelColorIndices[0x5f] << 4 | pixelColorIndices[0x5e],
                          CONCAT16(pixelColorIndices[0x5d] << 4 | pixelColorIndices[0x5c],
                                   CONCAT15(pixelColorIndices[0x5b] << 4 | pixelColorIndices[0x5a],
                                            CONCAT14(pixelColorIndices[0x59] << 4 | pixelColorIndices[0x58],
                                                     CONCAT13(pixelColorIndices[0x57] << 4 | pixelColorIndices[0x56],
                                                              CONCAT12(pixelColorIndices[0x55] << 4 |
                                                                       pixelColorIndices[0x54],
                                                                       CONCAT11(pixelColorIndices[0x53] << 4
                                                                                | pixelColorIndices[0x52],
                                                                                pixelColorIndices[0x51] << 4
                                                                                | pixelColorIndices[0x50]))))
                                           )));
     outputPtr[4] = CONCAT17(pixelColorIndices[0x4f] << 4 | pixelColorIndices[0x4e],
                          CONCAT16(pixelColorIndices[0x4d] << 4 | pixelColorIndices[0x4c],
                                   CONCAT15(pixelColorIndices[0x4b] << 4 | pixelColorIndices[0x4a],
                                            CONCAT14(pixelColorIndices[0x49] << 4 | pixelColorIndices[0x48],
                                                     CONCAT13(pixelColorIndices[0x47] << 4 | pixelColorIndices[0x46],
                                                              CONCAT12(pixelColorIndices[0x45] << 4 |
                                                                       pixelColorIndices[0x44],
                                                                       CONCAT11(pixelColorIndices[0x43] << 4
                                                                                | pixelColorIndices[0x42],
                                                                                pixelColorIndices[0x41] << 4
                                                                                | pixelColorIndices[0x40]))))
                                           )));
     *(byte *)(outputPtr + 7) = pixelColorIndices[0x70] | pixelColorIndices[0x71] << 4;
     *(byte *)((long)outputPtr + 0x39) = pixelColorIndices[0x72] | pixelColorIndices[0x73] << 4;
     *(byte *)((long)outputPtr + 0x3a) = pixelColorIndices[0x74] | pixelColorIndices[0x75] << 4;
     *(byte *)((long)outputPtr + 0x3b) = pixelColorIndices[0x76] | pixelColorIndices[0x77] << 4;
     dataOffset = 0xb6;
     outputPtr[1] = CONCAT17(pixelColorIndices[0x1f] << 4 | pixelColorIndices[0x1e],
                          CONCAT16(pixelColorIndices[0x1d] << 4 | pixelColorIndices[0x1c],
                                   CONCAT15(pixelColorIndices[0x1b] << 4 | pixelColorIndices[0x1a],
                                            CONCAT14(pixelColorIndices[0x19] << 4 | pixelColorIndices[0x18],
                                                     CONCAT13(pixelColorIndices[0x17] << 4 | pixelColorIndices[0x16],
                                                              CONCAT12(pixelColorIndices[0x15] << 4 |
                                                                       pixelColorIndices[0x14],
                                                                       CONCAT11(pixelColorIndices[0x13] << 4
                                                                                | pixelColorIndices[0x12],
                                                                                pixelColorIndices[0x11] << 4
                                                                                | pixelColorIndices[0x10]))))
                                           )));
     *outputPtr = CONCAT17(pixelColorIndices[0xf] << 4 | pixelColorIndices[0xe],
                        CONCAT16(pixelColorIndices[0xd] << 4 | pixelColorIndices[0xc],
                                 CONCAT15(pixelColorIndices[0xb] << 4 | pixelColorIndices[10],
                                          CONCAT14(pixelColorIndices[9] << 4 | pixelColorIndices[8],
                                                   CONCAT13(pixelColorIndices[7] << 4 | pixelColorIndices[6],
                                                            CONCAT12(pixelColorIndices[5] << 4 | pixelColorIndices[4]
                                                                     ,CONCAT11(pixelColorIndices[3] << 4 |
                                                                               pixelColorIndices[2],
                                                                               pixelColorIndices[1] << 4 |
                                                                               pixelColorIndices[0])))))));
     outputPtr[3] = CONCAT17(pixelColorIndices[0x3f] << 4 | pixelColorIndices[0x3e],
                          CONCAT16(pixelColorIndices[0x3d] << 4 | pixelColorIndices[0x3c],
                                   CONCAT15(pixelColorIndices[0x3b] << 4 | pixelColorIndices[0x3a],
                                            CONCAT14(pixelColorIndices[0x39] << 4 | pixelColorIndices[0x38],
                                                     CONCAT13(pixelColorIndices[0x37] << 4 | pixelColorIndices[0x36],
                                                              CONCAT12(pixelColorIndices[0x35] << 4 |
                                                                       pixelColorIndices[0x34],
                                                                       CONCAT11(pixelColorIndices[0x33] << 4
                                                                                | pixelColorIndices[0x32],
                                                                                pixelColorIndices[0x31] << 4
                                                                                | pixelColorIndices[0x30]))))
                                           )));
     outputPtr[2] = CONCAT17(pixelColorIndices[0x2f] << 4 | pixelColorIndices[0x2e],
                          CONCAT16(pixelColorIndices[0x2d] << 4 | pixelColorIndices[0x2c],
                                   CONCAT15(pixelColorIndices[0x2b] << 4 | pixelColorIndices[0x2a],
                                            CONCAT14(pixelColorIndices[0x29] << 4 | pixelColorIndices[0x28],
                                                     CONCAT13(pixelColorIndices[0x27] << 4 | pixelColorIndices[0x26],
                                                              CONCAT12(pixelColorIndices[0x25] << 4 |
                                                                       pixelColorIndices[0x24],
                                                                       CONCAT11(pixelColorIndices[0x23] << 4
                                                                                | pixelColorIndices[0x22],
                                                                                pixelColorIndices[0x21] << 4
                                                                                | pixelColorIndices[0x20]))))
                                           )));
     *(byte *)((long)outputPtr + 0x3c) = pixelColorIndices[0x78] | local_1cb << 4;
     encodeMode = 1;
     outputPtr[6] = CONCAT17(pixelColorIndices[0x6f] << 4 | pixelColorIndices[0x6e],
                          CONCAT16(pixelColorIndices[0x6d] << 4 | pixelColorIndices[0x6c],
                                   CONCAT15(pixelColorIndices[0x6b] << 4 | pixelColorIndices[0x6a],
                                            CONCAT14(pixelColorIndices[0x69] << 4 | pixelColorIndices[0x68],
                                                     CONCAT13(pixelColorIndices[0x67] << 4 | pixelColorIndices[0x66],
                                                              CONCAT12(pixelColorIndices[0x65] << 4 |
                                                                       pixelColorIndices[100],
                                                                       CONCAT11(pixelColorIndices[99] << 4 |
                                                                                pixelColorIndices[0x62],
                                                                                pixelColorIndices[0x61] << 4
                                                                                | pixelColorIndices[0x60]))))
                                           )));
   }
   *encodedData = encodeMode;
 LAB_0024a780:
   *outputSize = dataOffset + sizeValue;
   if (*(long *)(stackCanaryPtr + 0x28) != stackCanary) {
                     /* WARNING: Subroutine does not return */
     __stack_chk_fail();
   }
   return encodedData;
 }
 
 
 