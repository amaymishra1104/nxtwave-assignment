# Introduction to RAG

## Welcome to AI Memory

Imagine a student sitting in an exam hall. 
The student must answer all questions using only memory. 
The student cannot open any book. 
This is a closed-book exam. 
Standard artificial intelligence models work this way. 
An artificial intelligence model is a computer program that talks like a human. 
These models read huge amounts of text during training. 
They store facts inside their internal neural network weights. 
Neural network weights are the core digital memory numbers of the model. 
This internal memory is fixed. 
The model cannot update its own memory after training ends. 

## The Problem with Fixed Memory

Fixed memory creates two major problems. 
The first problem is old information. 
The world changes every single day. 
New rules and new college fees appear often. 
A fixed model does not know these new facts. 

The second problem is false answers. 
Sometimes the model forgets a real fact. 
The model then invents a fake answer. 
This is called hallucination. 
Hallucination means the model makes up false facts with high confidence. 
Students cannot trust these fake answers. 

## What is RAG?

RAG stands for Retrieval-Augmented Generation. 
RAG is a clever method to fix false answers. 
RAG lets the artificial intelligence model look at real documents before answering. 
This is like taking an open-book exam. 
The model reads a real book during the test. 
The model finds the correct paragraph. 
The model then writes the answer using that paragraph. 
RAG does not retrain the model. 
RAG does not change the core neural network weights of the model. 
The base model stays completely frozen. 
RAG only brings external text to the model. 

## Worked Example: College Admission Chatbot

Let us look at a real example from India. 
Priya finishes school in Delhi. 
Priya wants to join a local college. 
The college releases a large PDF notice about admission rules. 
Priya types a question into the college website chatbot. 
Priya asks about the last date to pay fees. 
The chatbot uses RAG to find the answer. 

## Step One: Chunking

The college PDF notice is very long. 
An artificial intelligence model cannot read a massive file all at once. 
The system uses chunking. 
Chunking is the process of breaking large source files into smaller text pieces. 
Each piece is called a chunk. 
One chunk contains only the fee rules. 
Another chunk contains only the hostel rules. 

## Step Two: Embeddings

Computers do not understand human words directly. 
Computers only understand math numbers. 
The system uses embeddings. 
Embeddings are dense numerical vectors representing the semantic meaning of text chunks. 
Semantic meaning means the actual topic of the text. 
Words with similar meanings get similar numbers. 

## Step Three: Vector Database

The system saves all these numerical vectors in a special storage place. 
This storage place is called a vector database. 
A vector database is a special digital filing cabinet that keeps all the text number lists safe and helps the computer look up matching ideas very quickly. 
When Priya asks her question, the system turns her question into numbers too. 
The system compares Priya's question numbers with the numbers in the vector database. 

## Step Four: Retrieval

The system searches the vector database for matching numbers. 
This step is called retrieval. 
Retrieval is the process of finding the most relevant text chunks from external storage. 
The system finds the exact chunk about fee dates. 

## Step Five: Augmenting the Prompt and Generation

The system now takes the user question and the retrieved text chunk. 
The system puts them together in one message. 
This step is called augmenting the prompt. 
Augmenting the prompt means adding retrieved source text directly into the input message before sending it to the model. 
The model reads this new combined message. 
The model performs generation. 
Generation is the process where the artificial intelligence model writes the final human-like response. 
The model reads the fee chunk and tells Priya the exact last date. 
The chatbot also shows the source citation. 
Source citation means telling the user the exact document name used for the answer. 

## Limitations of RAG

RAG is very powerful, but it has limits. 
The first limit is the retrieval bottleneck. 
The retrieval bottleneck happens when the system fails to find the correct document chunk. 
If the system misses the right chunk, the model cannot give the correct answer. 
The second limit is speed. 
Searching a database takes extra time. 
RAG can sometimes make the chatbot slower than a pure memory model. 

## Summary

Standard artificial intelligence models use closed-book memory and can hallucinate fake facts. 
RAG combines external document search with text generation. 
The system breaks documents into chunks and converts them into embeddings. 
A vector database stores these numbers and performs retrieval. 
The system then augments the prompt with the retrieved text. 
RAG keeps the base model frozen without changing any neural network weights. 

## Self-Check Questions

1. What does the term hallucination mean in artificial intelligence?
2. Why does RAG use chunking on large documents?
3. Does RAG retrain or change the core neural network weights of the model?