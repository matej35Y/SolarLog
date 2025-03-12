document.addEventListener('DOMContentLoaded', function() {
    // Set default date to today
    const today = new Date();
    const dateInput = document.getElementById('dateSelector');
    dateInput.value = today.toISOString().split('T')[0];
    
    // Add event listener to load button
    document.getElementById('loadBtn').addEventListener('click', loadDailyData);
    
    // Also load data when Enter is pressed in the date input
    dateInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            loadDailyData();
        }
    });
    
    // Load today's data on page load
    loadDailyData();
});

let hourlyChart = null;

function loadDailyData() {
    const date = document.getElementById('dateSelector').value;
    const resultsDiv = document.getElementById('results');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('errorMessage');
    
    // Show loading indicator
    resultsDiv.classList.add('d-none');
    loadingDiv.classList.remove('d-none');
    errorDiv.classList.add('d-none');
    
    // Fetch data from API
    fetch(`/api/analysis/by-date/${date}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Failed to load data');
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loading indicator
            loadingDiv.classList.add('d-none');
            
            // Populate summary data
            document.getElementById('summaryDate').textContent = date;
            document.getElementById('summaryEnergy').textContent = data.summary.total_energy_kwh;
            document.getElementById('summaryValue').textContent = data.summary.total_value;
            document.getElementById('summaryPrice').textContent = data.summary.arithmetic_avg_price_per_mwh;
            
            // Populate table
            const tableBody = document.getElementById('dataTable');
            tableBody.innerHTML = '';
            
            data.hourly_data.forEach(hour => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${hour.hour}</td>
                    <td>${hour.energy_kwh}</td>
                    <td>${hour.price_per_mwh}</td>
                    <td>${hour.value}</td>
                `;
                tableBody.appendChild(row);
            });
            
            // Create chart
            createHourlyChart(data.hourly_data);
            
            // Show results
            resultsDiv.classList.remove('d-none');
        })
        .catch(error => {
            loadingDiv.classList.add('d-none');
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        });
}

function createHourlyChart(hourlyData) {
    const ctx = document.getElementById('hourlyChart').getContext('2d');
    
    // Prepare data for chart
    const hours = hourlyData.map(item => item.hour);
    const energyData = hourlyData.map(item => item.energy_kwh);
    const priceData = hourlyData.map(item => item.price_per_mwh);
    const valueData = hourlyData.map(item => item.value);
    
    // Destroy previous chart if it exists
    if (hourlyChart) {
        hourlyChart.destroy();
    }
    
    // Create new chart
    hourlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours,
            datasets: [
                {
                    label: 'Energy (kWh)',
                    data: energyData,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Price (EUR/MWh)',
                    data: priceData,
                    type: 'line',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    fill: false,
                    yAxisID: 'y1'
                },
                {
                    label: 'Value (EUR)',
                    data: valueData,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1,
                    yAxisID: 'y2'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Energy (kWh)'
                    }
                },
                y1: {
                    beginAtZero: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Price (EUR/MWh)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                },
                y2: {
                    display: false,
                    beginAtZero: true
                }
            }
        }
    });
} 