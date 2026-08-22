import os
import pickle
import logging
from math import log
from difflib import get_close_matches
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from database.database import get_db
from database import data_crud

import config

class TextSearch:
    def __init__(self, index_file='data/index.pkl'):
        self.index = {}
        self.cache = {}
        self.doc_lengths = {}
        self.documents = {}
        self.avg_doc_length = 0
        os.makedirs(config.INDEX_FOLDER_PATH, exist_ok=True)
        self.cache_file = config.QUERY_CACHE_PATH
        self.index_file = os.path.join(config.INDEX_FOLDER_PATH, f"{index_file}_ivf.pkl")
        self.load_cache()
        self.load_index()
        self.data = None

    def add_document(self, doc_id, text):
        self.documents[doc_id] = text
        words = text.split()
        self.doc_lengths[doc_id] = len(words)
        for word in words:
            if word not in self.index:
                self.index[word] = set()
            self.index[word].add(doc_id)
        self.cache.clear() 
        self.save_cache()
        self.save_index()
        self.update_avg_doc_length()



    def add_data(self, table_name, text_columns, id_column, schema, db: Session = Depends(get_db)):
        """
        Adds data to the index by retrieving documents from the specified database table
        and processing them.
        Args:
            table_name (str): The name of the database table to query.
            text_columns (list): A list of column names containing text data to be indexed.
            id_column (str): The name of the column containing unique identifiers for the documents.
            schema (str): The schema name of the database table.
            db (Session, optional): The database session dependency. Defaults to Depends(get_db).
        Returns:
            list: A list of documents retrieved from the database.
        Raises:
            HTTPException: If an error occurs while adding data to the index.
        """
        try:
            # Retrieve data from the database
            documents = data_crud.query_table_with_columns(
                db=db,
                table_name=table_name,
                text_columns=text_columns,
                id_column=id_column,
                schema=schema
            )

            for doc in documents:
                try:
                    self.add_document(doc[0], doc[1])
                except Exception as e:
                    logging.info(f"Error processing document {doc}: {e}")

            self.data = documents
                
            return documents
        
        except Exception as e:
            logging.info(f"Error adding data to index: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def boolean_search(self, query):
        """
        Perform a boolean search on the indexed documents.
        This method takes a query string, splits it into individual words, and performs
        an intersection search across the indexed documents to find matches for all words
        in the query. If the query result is cached, it retrieves the result from the cache
        to improve performance.
        Args:
            query (str): The search query containing one or more words.
        Returns:
            list[dict]: A list of dictionaries, where each dictionary contains:
                - 'text' (str): The text of the matching document.
                - 'id' (int): The ID of the matching document.
        Notes:
            - The method uses a cache to store results of previous queries for faster retrieval.
            - If the query is empty, an empty list is returned.
            - The cache is updated and saved after processing a new query.
        """
        
        if query in self.cache:
            return self._docs_from_ids(self.cache[query])

        query_words = query.split()
        if not query_words:
            return []

        result = self.index.get(query_words[0], set())
        for word in query_words[1:]:
            result = result.intersection(self.index.get(word, set()))

        self.cache[query] = result
        self.save_cache()

        return self._docs_from_ids(result)

    def _docs_from_ids(self, doc_ids):
        return [{"text": self.documents[doc_id], "id": doc_id} for doc_id in doc_ids]

    def compute_tf_idf(self, query):
        query_words = query.split()
        if not query_words:
            return {}

        tf = {}
        for word in query_words:
            tf[word] = tf.get(word, 0) + 1

        idf = {}
        total_docs = len(set(doc_id for docs in self.index.values() for doc_id in docs))
        for word in query_words:
            doc_count = len(self.index.get(word, set()))
            idf[word] = log((total_docs + 1) / (doc_count + 1)) + 1

        tf_idf = {word: tf[word] * idf[word] for word in query_words}

        return tf_idf
    

    def ranked_search(self, query):
        """
        Perform a ranked search on the indexed documents based on the given query.
        This method computes the TF-IDF scores for the query terms, calculates the
        relevance scores for each document containing the query terms, and returns
        the documents ranked by their scores in descending order.
        Args:
            query (str): The search query string.
        Returns:
            list[dict]: A list of dictionaries representing the ranked search results.
                        Each dictionary contains:
                            - 'text' (str): The content of the document.
                            - 'score' (float): The relevance score of the document.
                            - 'id' (int): The unique identifier of the document.
        Notes:
            - If the query is empty, an empty list is returned.
            - The method assumes that `self.index` is a dictionary mapping words to
              document IDs and `self.documents` is a dictionary mapping document IDs
              to their content.
            - The `compute_tf_idf` method is expected to return a dictionary mapping
              query words to their TF-IDF scores.
        """

        tf_idf = self.compute_tf_idf(query)
        
        query_words = query.split()
        if not query_words:
            return []

        doc_scores = {}
        
        for word in query_words:
            if word in self.index:
                for doc_id in self.index[word]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + tf_idf[word]

        ranked_results = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)

        return [{
                'text': self.documents[doc_id],
                'score': score,
                'id': doc_id
            } 
            for doc_id, score in ranked_results]
    

    def boolean_ranked_search(self, query):
        """
        Perform a boolean and ranked search on the indexed documents.
        This method first performs a boolean search to find documents that match 
        all the words in the query. It then ranks the boolean-selected documents 
        using a TF-IDF scoring mechanism.
        Args:
            query (str): The search query containing one or more words.
        Returns:
            list[dict]: A list of dictionaries representing the ranked search results. 
                        Each dictionary contains:
                            - 'text' (str): The content of the document.
                            - 'score' (float): The TF-IDF score of the document.
                            - 'id' (int): The document ID.
        Notes:
            - If the query is found in the cache, the cached results are returned directly.
            - If the query is empty or no documents match, an empty list is returned.
            - The ranking is performed only on documents that match the boolean search criteria.
        """


        # boolean search
        if query in self.cache:
            return self._docs_from_ids(self.cache[query])

        query_words = query.split()
        if not query_words:
            return []

        result = self.index.get(query_words[0], set())
        for word in query_words[1:]:
            result = result.intersection(self.index.get(word, set()))

        # Perform ranked search on the boolean-selected documents
        query_words_initial = query.split()
        if not query_words_initial:
            return []

        # Filter query words to include only those present in the boolean-selected documents
        filtered_query_words = [word for word in query_words if word in self.index and self.index[word] & result]
        tf_idf = self.compute_tf_idf(" ".join(filtered_query_words))
    

        doc_scores = {}
        
        for word in filtered_query_words:
            for doc_id in result:  # Use only boolean-selected documents
                for word in filtered_query_words:
                    if word in self.index:
                        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + tf_idf[word]
        
        ranked_results = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)

        return [{
                'text': self.documents[doc_id],
                'score': score,
                'id': doc_id
            } 
                for doc_id, score in ranked_results]
    

    def boolean_bm25_search(self, query, k1=1.5, b=0.75):
        """
        Perform a combined Boolean and BM25 search on the indexed documents.
        This method first performs a Boolean search to narrow down the set of documents
        that contain all the words in the query. Then, it applies the BM25 ranking algorithm
        to score and rank the selected documents based on their relevance to the query.
        Args:
            query (str): The search query string containing one or more words.
            k1 (float, optional): The BM25 term frequency saturation parameter. Default is 1.5.
            b (float, optional): The BM25 length normalization parameter. Default is 0.75.
        Returns:
            list[dict]: A list of dictionaries representing the ranked search results. Each dictionary
            contains the following keys:
                - 'text' (str): The text of the document.
                - 'score' (float): The BM25 relevance score of the document.
                - 'id' (int): The document ID.
        Notes:
            - The method assumes that the `self.index` is a dictionary mapping words to sets of document IDs.
            - The `self.documents` is a dictionary mapping document IDs to their text content.
            - The `self.doc_lengths` is a dictionary mapping document IDs to their lengths.
            - The `self.avg_doc_length` is the average length of all documents.
            - The `self.cache` is used to store results of previous queries for faster retrieval.
        """

        # boolean search
        if query in self.cache:
            return self._docs_from_ids(self.cache[query])

        query_words = query.split()
        if not query_words:
            return []

        result = self.index.get(query_words[0], set())
        for word in query_words[1:]:
            result = result.intersection(self.index.get(word, set()))

        # Perform BM25 scoring on the boolean-selected documents
        total_docs = len(self.doc_lengths)
        avg_doc_length = self.avg_doc_length

        idf = {}
        for word in query_words:
            doc_count = len(self.index.get(word, set()))
            idf[word] = log((total_docs - doc_count + 0.5) / (doc_count + 0.5) + 1)

        doc_scores = {}
        for word in query_words:
            if word in self.index:
                for doc_id in result:  # Use only boolean-selected documents
                    tf = self.documents[doc_id].split().count(word)
                    score = idf[word] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (self.doc_lengths[doc_id] / avg_doc_length)))
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score

        ranked_results = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)

        return [{'text': self.documents[doc_id], 'score': score, 'id': doc_id} for doc_id, score in ranked_results]
    

    def bm25_search(self, query, k1=1.5, b=0.75):
        """
        Perform a BM25 search on the indexed documents using the given query.
        BM25 is a ranking function used by search engines to estimate the relevance
        of documents to a given search query. This implementation calculates the
        BM25 score for each document based on term frequency, inverse document
        frequency, and document length normalization.
        Args:
            query (str): The search query string.
            k1 (float, optional): Term frequency saturation parameter. Default is 1.5.
            b (float, optional): Length normalization parameter. Default is 0.75.
        Returns:
            list[dict]: A list of dictionaries containing the search results, where
            each dictionary has the following keys:
                - 'text' (str): The text of the document.
                - 'score' (float): The BM25 score of the document.
                - 'id' (int): The document ID.
        Notes:
            - The `self.index` is expected to be a dictionary where keys are words
              and values are sets of document IDs containing those words.
            - The `self.doc_lengths` is expected to be a dictionary mapping document
              IDs to their respective lengths.
            - The `self.avg_doc_length` is expected to be the average length of all
              documents.
            - The `self.documents` is expected to be a dictionary mapping document
              IDs to their respective text content.
        """

        query_words = query.split()
        if not query_words:
            return []

        total_docs = len(self.doc_lengths)
        avg_doc_length = self.avg_doc_length

        idf = {}
        for word in query_words:
            doc_count = len(self.index.get(word, set()))
            idf[word] = log((total_docs - doc_count + 0.5) / (doc_count + 0.5) + 1)

        doc_scores = {}
        for word in query_words:
            if word in self.index:
                for doc_id in self.index[word]:
                    tf = self.documents[doc_id].split().count(word)
                    score = idf[word] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (self.doc_lengths[doc_id] / avg_doc_length)))
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score

        ranked_results = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)
        
        return [{'text': self.documents[doc_id], 'score': score, 'id': doc_id }  for doc_id, score in ranked_results]
    

    def fuzzy_search(self, query, max_distance=2):
        """
        Perform a fuzzy search on the indexed documents based on the given query.
        This method splits the query into individual words and finds close matches
        for each word in the index using a fuzzy matching algorithm. It then retrieves
        the documents associated with the matched words.
        Args:
            query (str): The search query string to perform the fuzzy search on.
            max_distance (int, optional): The maximum edit distance for fuzzy matching.
                Defaults to 2. (Note: This parameter is not currently used in the implementation.)
        Returns:
            list: A list of dictionaries, where each dictionary contains:
                - 'text' (str): The text of the matched document.
                - 'id' (int): The ID of the matched document.
        Note:
            - The method uses `get_close_matches` from the `difflib` module to perform
              fuzzy matching.
            - If the query is empty, an empty list is returned.
        """

        query_words = query.split()
        if not query_words:
            return []

        matched_docs = set()
        for word in query_words:
            close_matches = get_close_matches(word, self.index.keys(), n=5, cutoff=0.8)
            for match in close_matches:
                if match in self.index:
                    matched_docs.update(self.index[match])

        return [{'text': self.documents[doc_id], 'id': doc_id}  for doc_id in matched_docs]
    

    def update_avg_doc_length(self):
        total_length = sum(self.doc_lengths.values())
        self.avg_doc_length = total_length / len(self.doc_lengths) if self.doc_lengths else 0

    def save_cache(self):
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def load_cache(self):
        try:
            with open(self.cache_file, 'rb') as f:
                self.cache = pickle.load(f)
        except (FileNotFoundError, EOFError):
            self.cache = {}

    def save_index(self):
        try:
            with open(self.index_file, 'wb') as f:
                pickle.dump({
                    'index': self.index,
                    'doc_lengths': self.doc_lengths,
                    'documents': self.documents,
                    'avg_doc_length': self.avg_doc_length
                }, f)
        except Exception as e:
            logging.error(f"Error saving index to file {self.index_file}: {e}")

    def load_index(self):
        try:
            with open(self.index_file, 'rb') as f:
                data = pickle.load(f)
                self.index = data.get('index', {})
                self.doc_lengths = data.get('doc_lengths', {})
                self.documents = data.get('documents', {})
                self.avg_doc_length = data.get('avg_doc_length', 0)

        except (FileNotFoundError, EOFError):
            self.index = {}
            self.doc_lengths = {}
            self.documents = {}
            self.avg_doc_length = 0

