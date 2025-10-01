let priceChart = null; // Variable to hold the Chart.js instance (needed to destroy/update the chart)

/**
 * Fetches price data for a given product and displays it as a chart.
 * This function is called when a user clicks 'View Price History' button.
 * * @param {number} productId - The ID of the product to track.
 * @param {string} productName - The name of the product.
 */
async function loadChart(productId, productName) {
    // 1. Update the chart title
    document.getElementById('chart-title').innerText = `Price History for: ${productName}`;

    // 2. Fetch data from the Flask API endpoint defined in app.py
    try {
        const response = await fetch(`/api/history/${productId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const historyData = await response.json();

        if (historyData.length === 0) {
            alert("No price history data found for this product.");
            return;
        }

        // 3. Prepare data for Chart.js
        // Extract the date/time for the X-axis labels
        const labels = historyData.map(item => item.date);  
        // Extract the price for the Y-axis data points
        const dataPoints = historyData.map(item => item.price); 

        // 4. Get the canvas element context
        const ctx = document.getElementById('priceChart').getContext('2d');

        // Destroy the previous chart instance if it exists (allows loading charts for different products)
        if (priceChart) {
            priceChart.destroy();
        }

        // 5. Create the new chart instance
        priceChart = new Chart(ctx, {
            type: 'line', // Line chart is best for visualizing data over time
            data: {
                labels: labels,
                datasets: [{
                    label: `Price (₹)`,
                    data: dataPoints,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.3, // Adds slight curve to the line
                    fill: false
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date Scraped'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price (₹)'
                        },
                        beginAtZero: false // Prices should reflect realistic range
                    }
                }
            }
        });

    } catch (error) {
        console.error("Failed to load price history:", error);
        alert("An error occurred while fetching the price data.");
    }
}
// static/script.js (Add to the bottom of the file)

document.addEventListener('DOMContentLoaded', () => {
    // Attach the event listener to the form when the page finishes loading
    const form = document.getElementById('addProductForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
});


async function handleFormSubmit(event) {
    event.preventDefault(); // Prevents the browser from doing a standard page reload
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Convert form data entries into a simple JSON object
    const data = {};
    formData.forEach((value, key) => data[key] = value);

    try {
        const response = await fetch('/api/product/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data) // Send the data to the Flask API
        });

        const result = await response.json();

        if (response.ok) {
            alert(result.message);
            form.reset(); // Clear the form
            // Reload the page to display the newly added product
            window.location.reload(); 
        } else {
            alert(`Error (${response.status}): ${result.message}`);
        }
    } catch (error) {
        console.error("Submission failed:", error);
        alert("An unknown error occurred during submission. Check console for details.");
    }
}