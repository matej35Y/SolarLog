document.addEventListener('DOMContentLoaded', function() {
    // Set default month to current month
    const today = new Date();
    const monthInput = document.getElementById('monthSelector');
    monthInput.value = `${today.getFullYear()}-${(today.getMonth() + 1).toString().padStart(2, '0')}`;
    
    // Add event listener to load button
    document.getElementById('loadBtn').addEventListener('click', loadMonthlyData);
    
    // Also load data when Enter is pressed in the month input
    monthInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            loadMonthlyData();
        }
    });
    
    // Load current month's data on page load
    loadMonthlyData();
});

let dailyChart = null;

function loadMonthlyData() {
    const month = document.getElementById('monthSelector').value;
    const resultsDiv = document.getElementById('results');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('errorMessage');
    
    // Show loading indicator
    resultsDiv.classList.add('d-none');
    loadingDiv.classList.remove('d-none');
    errorDiv.classList.add('d-none');
    
    // Fetch data from API
    fetch(`/api/analysis/by-month/${month}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || err.message || 'Failed to load data');
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loading indicator
            loadingDiv.classList.add('d-none');
            
            // Check if we have data or just a status message
            if (data.status === 'no_data') {
                throw new Error(data.message);
            }
            
            // Format month name for display
            const [year, monthNum] = month.split('-');
            const monthDate = new Date(year, parseInt(monthNum) - 1, 1);
            const monthName = monthDate.toLocaleString('default', { month: 'long' });
            
            // Get summary data
            const summary = data.month_summary || {};
            const totalValue = summary.total_value || 0;
            const totalEnergy = summary.total_energy_mwh || 0;
            const avgPrice = summary.avg_working_hour_price || 0;
            const daysWithData = summary.days_with_data || 0;
            const workingHours = summary.total_working_hours || 0;
            
            // Populate summary data
            document.getElementById('summaryMonth').textContent = `${monthName} ${year}`;
            document.getElementById('summaryValue').textContent = totalValue;
            document.getElementById('summaryEnergy').textContent = totalEnergy;
            document.getElementById('summaryPrice').textContent = avgPrice;
            document.getElementById('summaryDays').textContent = daysWithData;
            document.getElementById('summaryHours').textContent = workingHours;
            
            // Prepare data for chart and table
            const dailyData = Object.entries(data)
                .filter(([key]) => key !== 'month_summary')
                .map(([date, info]) => ({
                    date: date,
                    value: info.total_value,
                    energy: info.total_energy_mwh,
                    price: info.avg_working_hour_price,
                    hours: info.working_hours
                }))
                .sort((a, b) => a.date.localeCompare(b.date));
            
            // Populate table
            const tableBody = document.getElementById('dataTable');
            tableBody.innerHTML = '';
            
            dailyData.forEach(day => {
                const row = document.createElement('tr');
                const formattedDate = new Date(day.date).toLocaleDateString();
                row.innerHTML = `
                    <td>${formattedDate}</td>
                    <td>${day.energy} MWh</td>
                    <td>${day.price} EUR/MWh</td>
                    <td>${day.value} EUR</td>
                    <td><a href="/ui/daily?date=${day.date}" class="btn btn-sm btn-outline-primary">View Details</a></td>
                `;
                tableBody.appendChild(row);
            });
            
            // Create chart
            createDailyChart(dailyData);
            
            // Show results
            resultsDiv.classList.remove('d-none');
        })
        .catch(error => {
            loadingDiv.classList.add('d-none');
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        });
}

function createDailyChart(dailyData) {
    const ctx = document.getElementById('dailyChart').getContext('2d');
    
    // Prepare data for chart
    const dates = dailyData.map(item => new Date(item.date).toLocaleDateString());
    const values = dailyData.map(item => item.value);
    const energyData = dailyData.map(item => item.energy);
    
    // Destroy previous chart if it exists
    if (dailyChart) {
        dailyChart.destroy();
    }
    
    // Create new chart
    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Daily Value (EUR)',
                    data: values,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Energy Production (MWh)',
                    data: energyData,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    type: 'line',
                    yAxisID: 'y1'
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
                        text: 'Value (EUR)'
                    }
                },
                y1: {
                    beginAtZero: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Energy (MWh)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
} 