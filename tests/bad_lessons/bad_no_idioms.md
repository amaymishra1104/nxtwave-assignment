# Introduction to RAG (Retrieval-Augmented Generation)

When you're studying for AI, you don't want to bite the bullet and learn everything the hard way. 
Think of RAG as a silver bullet that lets your chatbot hit the ground running. 
Instead of beating around the bush, RAG spills the beans by letting the model keep its cards on the table. 
In this lesson, we will see how RAG is the best thing since sliced bread. 

---

## 1. What is an LLM and Why Does it Need Help?

An LLM is a Large Language Model. 
In simple words, an LLM is a smart computer program trained on large amounts of text. 
Sometimes models make up facts out of the blue, called a hallucination. 
A hallucination means an AI gives an incorrect answer with high confidence. 
Instead of barking up the wrong tree, we use RAG to give it fresh notes. 

---

## 2. What is RAG?

RAG combines two steps:
1. **Retrieval**: Finding and fetching information from an outside document. 
2. **Generation**: The process where an AI produces a natural language answer. 

RAG does not retrain the internal neural network weights of the model. 

---

## 3. How RAG Works Step by Step

### Step A: Chunking the Documents
A context window is the maximum amount of text an AI model can read at one time. 
To keep things from getting out of hand, we use chunking. 
Chunking means dividing a large document into smaller, bite-sized sections. 

### Step B: Creating Embeddings and Vectors
An embedding is a list of numbers that represents the meaning of text. 
This list of numbers is called a vector. 
A vector shows the meaning of a sentence in mathematical space. 

### Step C: Storing in a Vector Database
A vector database is a specialized storage system designed to store vectors and find similar ideas rapidly. 

### Step D: Augmenting the Prompt and Generating the Answer
A prompt is the input question you give to an AI model. 
To augment means adding extra relevant facts into the prompt. 

---

## 4. Real-World Worked Example: College Admission Chatbot in India

Imagine Rahul is a student applying to Delhi State University. 
Rahul asks the chatbot about the exam deadline. 
1. The chatbot hits the nail on the head by finding paragraph 14 in the circular. 
2. It augments the prompt with the exact notice text. 
3. The AI answers: *"The last date to submit is November 15."*

---

## 5. Limitations of RAG

1. If retrieval fails, you're back to square one. 
2. Searching adds extra latency. 

---

## 6. Lesson Summary

* Plain models can guess wrongly when pushed to the wall. 
* RAG gives the model an open book to save the day. 

---

## 7. Self-Check Questions

1. Why is RAG like an open-book exam?
2. Does RAG retrain the model weights?
3. What is chunking?

