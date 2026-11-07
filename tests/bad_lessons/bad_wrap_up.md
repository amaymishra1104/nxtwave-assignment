# Introduction to RAG (Retrieval-Augmented Generation)

Have you ever taken an exam? 
In an open-book test, the teacher allows you to keep your textbook open. 
You can search the book for the right page and write an answer. 
In this lesson, you will learn about RAG. 
RAG stands for Retrieval-Augmented Generation. 
It helps an AI look up facts in documents before it answers you. 

---

## 1. What is an LLM and Why Does it Need Help?

An LLM is a Large Language Model. 
In simple words, an LLM is a smart computer program trained on large amounts of text. 
An AI can produce a hallucination. 
A hallucination means an AI gives an incorrect or fake answer with high confidence. 
RAG solves this problem by providing external documents. 

---

## 2. What is RAG?

RAG combines two steps:
1. **Retrieval**: Finding and fetching the most relevant piece of information from an outside document. 
2. **Generation**: The process where an AI produces a natural language answer using its writing abilities. 
RAG never retrains or changes the internal neural network weights of the model. 

---

## 3. How RAG Works Step by Step

### Step A: Chunking the Documents
A context window is the maximum amount of text an AI model can read at one time. 
Chunking means dividing a large document into smaller, bite-sized sections. 

### Step B: Creating Embeddings and Vectors
An embedding is a list of numbers that represents the meaning of text. 
This list of numbers is called a vector. 
A vector shows the meaning of a sentence in mathematical space. 

### Step C: Storing in a Vector Database
A vector database is a specialized storage system designed to store vectors and find similar ideas rapidly. 

### Step D: Augmenting the Prompt and Generating the Answer
A prompt is the input question you give to an AI model. 
To augment means adding extra relevant facts into the prompt to help the AI answer accurately. 
The AI model reads the question and facts together to generate the answer. 

---

## 4. Real-World Worked Example: College Admission Chatbot in India

Imagine Rahul is a student applying to Delhi State University. 
Rahul types a question into the college website chatbot: 
> *"What is the last date to submit the exam form for regular students?"*

1. **Retrieval**: The chatbot searches the circular PDF and finds page 12. 
2. **Augmenting the Prompt**: It puts the notice into the prompt for the AI. 
3. **Generation**: The AI replies: *"The last date is November 15."*

---

## 5. Limitations of RAG

1. If retrieval fails, the answer will be wrong. 
2. Searching adds extra latency. 

And that is everything you need to know about RAG. Good luck with your AI journey!

