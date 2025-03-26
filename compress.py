#!/usr/bin/env python3
"""
Compress text using LLMLingua.

This script reads text from an input file, compresses it using LLMLingua,
and writes the compressed text to an output file.

Usage:
    python compress.py input.txt output.txt
    
Options:
    --ratio RATIO        Compression ratio (default: 0.5)
    --verbose            Print compression stats to stderr
    --help               Show this help message and exit
"""

import sys
import argparse
from llmlingua import PromptCompressor
import time
import os
import torch  # Add torch import

# Force CPU usage before importing other libraries that might use torch
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

def parse_args():
    parser = argparse.ArgumentParser(description="Compress text using LLMLingua")
    parser.add_argument("input_file", type=str, help="Input file to compress")
    parser.add_argument("output_file", type=str, help="Output file for compressed text")
    parser.add_argument("--ratio", type=float, default=0.5,
                        help="Compression ratio (default: 0.5)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print compression stats to stderr")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Initialize LLMLingua with default model
    try:
        if args.verbose:
            print("Initializing LLMLingua...", file=sys.stderr)
        # Explicitly force CPU
        llm_lingua = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True, # Whether to use llmlingua-2
            device_map="mps")
        
        # Read from input file
        if args.verbose:
            print(f"Reading text from {args.input_file}...", file=sys.stderr)
        with open(args.input_file, 'r', encoding='utf-8') as f:
            input_text = f.read()
        
        if args.verbose:
            print(f"Input text length: {len(input_text)} characters", file=sys.stderr)
            start_time = time.time()
        
        # Compress the text
        if args.verbose:
            print(f"Compressing text with target ratio: {args.ratio}...", file=sys.stderr)
        compressed_result = llm_lingua.compress_prompt(
            input_text, 
            # question="What does this codebase do?",
            rate=args.ratio,
            # condition_compare=True,
            # condition_in_question="after",
            # rank_method="longllmlingua",
            # use_sentence_level_filter=False,
            # use_token_level_filter=False,
            # context_budget="+100",
            dynamic_context_compression_ratio=args.ratio,  # enable dynamic_context_compression_ratio
            # reorder_context="sort",
        )
        
        compressed_text = compressed_result["compressed_prompt"]
        
        if args.verbose:
            end_time = time.time()
            print(f"Compressed text length: {len(compressed_text)} characters", file=sys.stderr)
            print(f"Compression ratio achieved: {len(compressed_text)/len(input_text):.2f}", file=sys.stderr)
            print(f"Compression time: {end_time - start_time:.2f} seconds", file=sys.stderr)
        
        # Write to output file
        if args.verbose:
            print(f"Writing compressed text to {args.output_file}...", file=sys.stderr)
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(compressed_text)
            
        if args.verbose:
            print("Compression complete!", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during compression: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
