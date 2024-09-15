// apiService.js
const API_URL = 'http://localhost:8000';

export const sendQuery = async (query) => {
  const response = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error('Network response was not ok');
  }

  return response.json();
};
