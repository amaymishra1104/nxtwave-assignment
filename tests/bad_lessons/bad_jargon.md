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
An LLM is a smart computer program trained on text. 
Standard models can produce a hallucination. 
A hallucination means an AI gives an incorrect answer with confidence. 

---

## 2. What is RAG?

RAG combines two steps:
1. Retrieval: finding information from an outside document. 
2. Generation: producing an answer with an AI. 
RAG does not retrain model weights. 

---

## 3. How RAG Works Step by Step

We immediately run chunking across all corpus documents. 
Then we calculate the embedding for every single sentence. 
All high-dimensional vectors are stored in our vector database. 
When a student types a query, we calculate the nearest neighbor in the vector database. 
Then we augment the prompt and generate the response. 

---

## 4. Real-World Worked Example: College Admission Chatbot in India

Rahul asks the Delhi State University chatbot about the exam deadline. 
1. Retrieval: The system searches the circular and finds paragraph 14. 
2. Augmenting: The text is appended to the prompt. 
3. Generation: The AI answers with the deadline. 

---

## 5. Limitations of RAG

1. If retrieval fails, the answer will be wrong. 
2. External lookups add extra latency. 

---

## 6. Lesson Summary

* RAG searches external documents before answering. 
* It stops hallucinations without retraining weights. 

---

## 7. Self-Check Questions

1. What is an open-book exam analogy?
2. Does RAG retrain the model weights?
3. What is one limitation of RAG?
