const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const sendQuery = async (query) => {
  try {
    const response = await fetch(`${BASE_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `HTTP error! Status: ${response.status}`);
    }
    return data;
  } catch (error) {
    console.error('Error in sendQuery:', error);
    throw error;
  }
};

export const fetchSalesData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/sales`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in fetchSalesData:', error);
    throw error;
  }
};

export const fetchQueriesData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/products`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error in fetchQueriesData:', error);
    throw error;
  }
};

const requestJson = async (path, options = {}) => {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP error! Status: ${response.status}`);
  }
  return data;
};

export const submitFeedback = (feedback) =>
  requestJson('/feedback', { method: 'POST', body: JSON.stringify(feedback) });

export const fetchFeedback = (rating = 'all') =>
  requestJson(`/feedback?rating=${encodeURIComponent(rating)}`);

export const reviewFeedback = (id, review) =>
  requestJson(`/feedback/${id}`, { method: 'PATCH', body: JSON.stringify(review) });

export const fetchEvalDataset = () => requestJson('/eval/dataset');

export const fetchEvalResults = () => requestJson('/eval/results');

export const runRoutingEval = () => requestJson('/eval/run', { method: 'POST' });

export const fetchPracticeQuestions = async () => {
  try {
    const response = await fetch(`${BASE_URL}/practice-questions`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    const data = await response.json();
    return data.questions || [];
  } catch (error) {
    console.error('Error in fetchPracticeQuestions:', error);
    throw error;
  }
};
