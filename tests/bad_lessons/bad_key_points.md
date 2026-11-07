# Introduction to RAG (Retrieval-Augmented Generation)

Have you ever taken an exam? 
In an open-book test, you can search your textbook and write a correct answer. 
RAG stands for Retrieval-Augmented Generation. 
It helps an AI look up facts in documents before it answers you. 

---

## 1. What is an LLM and Why Does it Need Help?

An LLM is a Large Language Model. 
In simple words, an LLM is a smart computer program trained on large amounts of text. 
Standard models have two big problems. 
First, their memory stops on the day their training finishes. 
Second, an AI can produce a hallucination. 
A hallucination means an AI gives an incorrect or fake answer with high confidence. 
RAG solves this by providing external documents. 

---

## 2. What is RAG?

RAG combines two steps:
1. **Retrieval**: Finding and fetching the most relevant piece of information from an outside document. 
2. **Generation**: The process where an AI produces a natural language answer using its writing abilities. 
RAG never retrains or changes the internal model weights. 

---

## 3. How RAG Works

When a student asks a question, the system searches the text files directly. 
Then, it takes the user question and adds the found text to it. 
To augment means adding extra relevant facts into the prompt to help the AI answer accurately. 
A prompt is the input question and instructions you give to an AI model. 
Finally, the AI reads the text and generates an answer. 

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

1. If retrieval finds the wrong text, the answer will be wrong. 
2. Searching external files takes extra time. 

---

## 6. Lesson Summary

* RAG gives the AI an open book of trusted external notes. 
* The system retrieves facts and adds them to the user prompt. 
* This method stops false guesses without model retraining. 

---

## 7. Self-Check Questions

1. What is the difference between a closed-book test and RAG?
2. What does augment mean in RAG?
3. Does RAG retrain the model weights?

