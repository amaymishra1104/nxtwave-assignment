# Introduction to RAG (Retrieval-Augmented Generation)

Have you ever taken an exam? 
In an open-book test, the teacher allows you to keep your textbook open. 
You search the book for the right page and write a correct answer. 
In this lesson, you will learn about a tool called RAG. 
RAG stands for Retrieval-Augmented Generation. 
It helps an AI look up facts in documents before it answers you. 

---

## 1. What is RAG?

RAG combines two steps:
1. **Retrieval**: Finding and fetching the most relevant piece of information from an outside document. 
2. **Generation**: The process where an AI produces a natural language answer using its writing abilities. 

RAG does not retrain the AI. 
It never changes the internal brain weights of the model. 

---

## 2. How RAG Works Step by Step

### Step A: Chunking the Documents
Every AI has a context window. 
A context window is the maximum amount of text an AI model can read at one time. 
To solve this, we use chunking. 
Chunking means dividing a large document into smaller, bite-sized sections. 

### Step B: Creating Embeddings and Vectors
We convert each text chunk into an embedding. 
An embedding is a list of numbers that represents the meaning of text. 
This list of numbers is called a vector. 
A vector shows the meaning of a sentence in mathematical space. 

### Step C: Storing in a Vector Database
Next, we save these numbers into a vector database. 
A vector database is a specialized storage system designed to store vectors and find similar ideas rapidly. 
When a student asks a question, the system finds matching chunks. 

### Step D: Augmenting the Prompt and Generating the Answer
A prompt is the input question you give to an AI model. 
The system takes the user question and adds the retrieved facts to it. 
To augment means adding extra relevant facts into the prompt to help the AI answer accurately. 
An AI can produce a hallucination. 
A hallucination means an AI gives an incorrect or fake answer with high confidence. 
RAG reduces this hallucination. 

---

## 3. Real-World Worked Example: College Admission Chatbot in India

Imagine Rahul is a student applying to Delhi State University. 
Rahul types a question into the college website chatbot: 
> *"What is the last date to submit the exam form for regular students?"*

1. **Retrieval**: The chatbot finds page 12 of the circular: *"Last date is November 15."*
2. **Augmenting**: Adds the notice to the prompt. 
3. **Generation**: The AI writes back with the exact date. 

---

## 4. Limitations of RAG

1. If your search brings the wrong paragraph, the AI cannot answer correctly. 
2. Searching takes extra time. 

---

## 5. Lesson Summary

* Large documents are broken into chunks and stored as vectors. 
* The system retrieves facts and adds them to the prompt. 

---

## 6. Self-Check Questions

1. What does RAG stand for?
2. What is chunking?
3. What is a vector database?
