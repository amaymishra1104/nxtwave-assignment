# Introduction to Retrieval-Augmented Generation (RAG)

## Welcome to Your AI Journey

You want to build a career in AI. 
This lesson will teach you a powerful tool called RAG. 
RAG stands for Retrieval-Augmented Generation. 
This is a method that helps artificial intelligence give correct answers. 

## The Closed-Book Exam Problem

Imagine you are sitting in a tough college exam. 
The teacher takes away all your textbooks. 
The teacher tells you to answer every question from your memory alone. 
This is a closed-book exam. 

If you forget a date or a rule, what do you do? 
You might guess the answer. 
Sometimes your guess is completely wrong. 
You sound very confident. 
However, your answer is fake. 

Standard AI models work just like this closed-book exam. 
These AI models have learned many things during their training. 
Their internal memory is fixed. 
This internal memory is called parametric memory. 
The AI model relies only on this fixed memory to answer your questions. 

## What is Hallucination?

When an AI model does not know the true answer, it makes up a fake fact. 
In AI, this problem is called a hallucination. 
A hallucination happens when the AI sounds very smart while telling a lie. 
Standard AI models often hallucinate when you ask about new facts. 
They also hallucinate when you ask about private data. 
They do not know what they do not know. 

## The Open-Book Solution: What is RAG?

Now imagine a different exam. 
The teacher lets you bring your textbooks into the hall. 
When a question comes, you open the right book first. 
You read the correct page. 
Then you write your answer using the facts from that page. 
This is an open-book exam. 

RAG is the open-book method for AI. 
RAG does not change the core AI model. 
It does not touch the internal memory weights of the model. 
Instead, RAG keeps a separate library of documents outside the AI. 
This external library is called non-parametric memory. 
When you ask a question, RAG finds the exact text you need. 
Then RAG gives this text to the AI model. 
The AI reads the text and writes a truthful answer. 

## Worked Example: College Admission Chatbot

Let us look at a real example from India. 
You apply for a seat in a local college. 
The college releases a brand new PDF notice about admission rules. 
The college wants a chatbot to answer student questions. 

If you use a standard AI model, it will fail. 
The standard AI model was trained last year. 
It has never seen the new admission PDF notice. 
It will guess the dates and fees. 
It will hallucinate wrong facts. 

If you use RAG, the system works in clear steps. 
Let us walk through each step. 

## Step-by-Step RAG Pipeline

### 1. Chunking

The college admission PDF notice is very long. 
An AI model cannot read a massive file all at once. 
So we use chunking. 
Chunking is the process of cutting a large text document into small, readable pieces. 
Each small piece is called a text chunk. 

### 2. Embeddings

Next, the system must understand what each text chunk means. 
Computers only understand numbers. 
So we use embeddings. 
Embeddings are lists of math numbers that capture the true meaning of text chunks so the computer can compare them easily. 
Sentences with similar meanings get numbers that are close to each other. 

### 3. Vector Database

Where do we store these math numbers? 
We store them in a special computer folder. 
This folder is called a vector database. 
A vector database is a special database that indexes high-dimensional embeddings to perform fast similarity search across millions of text chunks. 
It helps the computer find matching topics in milliseconds. 

### 4. Retrieval

Now a student types a question. 
The student asks, "What is the last date to pay fees?" 
The system turns this question into math numbers. 
Then it searches the vector database. 
It finds the exact text chunk about the fee payment date. 
This step is called retrieval. 
Retrieval is the act of searching an external database to find the most relevant text passages for a given question. 

### 5. Augmenting the Prompt

Now the system has the user question. 
It also has the correct text chunk from the college PDF notice. 
Next, the system combines both items together. 
This step is called augmenting the prompt. 
Augmenting the prompt means adding the retrieved text passages directly into the input message along with the user question. 

### 6. Generation

Finally, the system sends this augmented prompt to the AI model. 
The AI model reads the question. 
It reads the exact college notice text provided in the prompt. 
Then it writes a clear, correct answer for the student. 
This final step is called generation. 
Generation is the process where the AI model creates a human-like response based on the input text. 

## Why RAG is Powerful

RAG fixes the big limits of AI. 

First, RAG stops hallucinations. 
The AI grounds its answers in real source text. 

Second, RAG gives source proof. 
Because the AI reads an external file, it can show the exact document name to the user. 

Third, RAG saves time and money. 
You do not need to retrain the huge AI model when college rules change. 
You only update the files inside your vector database. 

## Limitations of RAG

RAG is great, but it has some limits. 

One limit is the retrieval bottleneck. 
If the retrieval step fails to find the right text chunk, the AI cannot give the right answer. 
The AI can only work with the text it receives. 

Another limit is speed. 
Searching a database takes a small amount of extra time. 
This creates a slight delay in answering the user. 

## Summary

- Standard AI models act like a closed-book exam and often hallucinate. 
- RAG acts like an open-book exam by using external documents. 
- RAG uses **chunking** to cut large files into small pieces. 
- RAG uses **embeddings** to turn text into math numbers. 
- RAG stores these numbers in a **vector database**. 
- RAG uses **retrieval** to find the correct text for a question. 
- RAG performs **prompt augmentation** to give the text and question to the AI. 
- RAG achieves safe **generation** without retraining the AI model weights. 

## Self-Check Questions

1. What is the main problem that happens when a standard AI model has to answer questions without external documents?
2. What does a vector database store, and what purpose does it serve in the RAG process?
3. If the retrieval step fails to find the correct text chunk from a document, what happens to the final answer generated by the AI?