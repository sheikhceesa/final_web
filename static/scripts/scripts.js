document.addEventListener('DOMContentLoaded', function () {
  // Connect to the Socket.IO server
  const socket = io();

  // Main chart variables
  let fillRateChart,
      investmentCostChart,
      totalAutonomyChart,
      stockVolumeChart,
      stockageRatioChart,
      capexTotalChart;

  let allSiteData = [];

  // Predefined color palette
  const colorPalette = [
    '#e41a1c', '#377eb8', '#4daf4a', '#984ea3',
    '#ff7f00', '#ffff33', '#a65628', '#f781bf',
    '#999999', '#66c2a5', '#fc8d62', '#8da0cb'
  ];
  function getColor(index) {
    return colorPalette[index % colorPalette.length];
  }

  // Register Data Labels plugin globally (disabled in datasets)
  Chart.register(ChartDataLabels);

  // Populate the site filter dropdown
  function populateSiteFilter(sites) {
    const siteFilter = document.getElementById('siteFilter');
    siteFilter.innerHTML = '';
    sites.forEach((site, index) => {
      const option = document.createElement('option');
      option.value = index;
      option.text = site;
      option.selected = true;
      siteFilter.appendChild(option);
    });
  }

  // Populate the year filter checkboxes
  function populateYearFilter(years) {
    const yearFilter = document.getElementById('yearFilter');
    yearFilter.innerHTML = '';
    years.forEach(year => {
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = 'year_' + year;
      checkbox.value = year;
      checkbox.checked = true;
      const label = document.createElement('label');
      label.htmlFor = 'year_' + year;
      label.textContent = year;
      const wrapper = document.createElement('div');
      wrapper.classList.add('year-checkbox');
      wrapper.appendChild(checkbox);
      wrapper.appendChild(label);
      yearFilter.appendChild(wrapper);
    });
  }

  // Event Listeners for Filters
  document.getElementById('selectAllSitesBtn').addEventListener('click', selectAllSites);
  document.getElementById('selectAllYearsBtn').addEventListener('click', selectAllYears);
  document.getElementById('siteFilter').addEventListener('change', updateCharts);
  document.getElementById('yearFilter').addEventListener('change', updateCharts);

  // PDF Download: Hide non-graph elements and capture high-res image (scale 4)
  document.getElementById('downloadPDFButton').addEventListener('click', function () {
    // Hide non-graph elements temporarily
    const elementsToHide = document.querySelectorAll('header, .filters, .map-container, .info-blocks, .update-info, #downloadPDFButton');
    const previousStyles = [];
    elementsToHide.forEach((el, i) => {
      previousStyles[i] = el.style.display;
      el.style.display = 'none';
    });

    // Set the container background to white for better print quality
    const container = document.querySelector('.container');
    const prevContainerBG = container.style.backgroundColor;
    container.style.backgroundColor = '#fff';

    // Wait for all charts to finish rendering
    const charts = [fillRateChart, investmentCostChart, totalAutonomyChart, stockVolumeChart, stockageRatioChart, capexTotalChart];
    let chartsRendered = 0;

    charts.forEach(chart => {
      if (chart) {
        chart.options.animation = false; // Disable animations for rendering
        chart.update('none'); // Update charts without animations
        chart.options.animation = true; // Re-enable animations
        chartsRendered++;
      }
    });

    // Wait for charts to finish rendering
    setTimeout(() => {
      // Use html2canvas to capture the container
      html2canvas(container, {
        scale: 4, // Increase scale for higher resolution
        useCORS: true, // Allow cross-origin images
        logging: true, // Enable logging for debugging
        allowTaint: true, // Allow tainted canvases
        backgroundColor: null, // Ensure no background color covers the graphs
        windowWidth: container.scrollWidth, // Capture the full width
        windowHeight: container.scrollHeight // Capture the full height
      }).then(function (canvas) {
        // Restore hidden elements and container background
        elementsToHide.forEach((el, i) => {
          el.style.display = previousStyles[i];
        });
        container.style.backgroundColor = prevContainerBG;

        // Convert canvas to image
        const imgData = canvas.toDataURL('image/png', 1.0); // Highest quality

        // Create a PDF
        const pdf = new jspdf.jsPDF('p', 'pt', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = pdf.internal.pageSize.getHeight();
        const ratio = canvas.width / pdfWidth;
        const imgHeight = canvas.height / ratio;

        // Split the image into multiple pages if it's too tall
        let heightLeft = imgHeight;
        let position = 0;

        // Add the first page
        pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
        heightLeft -= pdfHeight;

        // Add additional pages if needed
        while (heightLeft > 0) {
          position = heightLeft - imgHeight;
          pdf.addPage();
          pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
          heightLeft -= pdfHeight;
        }

        // Save the PDF
        pdf.save('dam_data_visualization.pdf');
      }).catch(function (error) {
        console.error('Error generating PDF:', error);
        // Restore hidden elements and container background in case of error
        elementsToHide.forEach((el, i) => {
          el.style.display = previousStyles[i];
        });
        container.style.backgroundColor = prevContainerBG;
      });
    }, 500); // Wait 500ms for charts to render
  });

  function selectAllSites() {
    const siteFilterElement = document.getElementById('siteFilter');
    Array.from(siteFilterElement.options).forEach(option => option.selected = true);
    updateCharts();
  }

  function selectAllYears() {
    document.querySelectorAll('#yearFilter input').forEach(input => input.checked = true);
    updateCharts();
  }

  function createOrUpdateCharts(newData) {
    if (!newData || !newData.length) {
      document.getElementById('error-container').textContent = 'No data available.';
      return;
    }
    const now = new Date();
    document.getElementById('lastUpdate').textContent = now.toLocaleString();
    newData.forEach(newItem => {
      const idx = allSiteData.findIndex(item => item.sites === newItem.sites);
      if (idx !== -1) {
        allSiteData[idx] = newItem;
      } else {
        allSiteData.push(newItem);
      }
    });
    populateSiteFilter(allSiteData.map(item => item.sites || 'Unknown Site'));
    populateYearFilter(['2022','2023','2024','2025','2026','2027','2028','2029','2030']);
    updateCharts();
  }

  function updateCharts() {
    const siteFilterElement = document.getElementById('siteFilter');
    const selectedSiteIndices = Array.from(siteFilterElement.selectedOptions).map(option => parseInt(option.value));
    if (!selectedSiteIndices.length) {
      document.getElementById('error-container').textContent = 'No sites selected.';
      clearCharts();
      return;
    }
    document.getElementById('error-container').textContent = '';
    const filteredData = selectedSiteIndices.map(index => allSiteData[index]);
    const selectedYears = Array.from(document.querySelectorAll('#yearFilter input:checked')).map(input => input.value);
    if (!selectedYears.length) {
      document.getElementById('error-container').textContent = 'No years selected.';
      clearCharts();
      return;
    }
    document.getElementById('error-container').textContent = '';

    // Replace null values with 0 in the dataset
    const replaceNullWithZero = value => value === null ? 0 : value;
    const sites = filteredData.map(item => item.sites || 'Unknown Site');
    const totalCapacity  = filteredData.map(item => replaceNullWithZero(item.total_capacity));
    const stockVolume    = filteredData.map(item => replaceNullWithZero(item.stock_volume));
    const globalFillRate = filteredData.map(item => replaceNullWithZero(item.global_fill_rate));
    const partialFillRate = filteredData.map(item => replaceNullWithZero(item.partial_fill_rate));
    const totalAutonomy  = filteredData.map(item => replaceNullWithZero(item.total_autonomy));
    const partialAutonomy = filteredData.map(item => replaceNullWithZero(item.partial_autonomy));
    const stockageRatio  = filteredData.map(item => replaceNullWithZero(item.stockage_ratio));

    // CAPEX Investment Cost datasets for Chart 2
    const capexDatasets = filteredData.map((siteData, index) => {
      const capexValues = selectedYears.map(year => {
        const field = 'capex_' + year;
        return replaceNullWithZero(siteData[field]);
      });
      return {
        label: siteData.sites || 'Unknown Site',
        data: capexValues,
        borderColor: getColor(index),
        backgroundColor: 'rgba(0,0,0,0)',
        borderWidth: 2,
        fill: false,
        tension: 0.1,
        hidden: false,
        datalabels: { display: false }
      };
    });
    
    // For Chart 6: Total CAPEX, use field total_capex
    const totalCapexData = filteredData.map(siteData => replaceNullWithZero(siteData.total_capex));

    // Compute scaling values for main charts
    const maxFillRate = Math.max(...globalFillRate.concat(partialFillRate));
    const fillRateMaxScale = maxFillRate + (maxFillRate * 0.1);
    const maxTotalAutonomy = Math.max(...totalAutonomy);
    const autonomyMaxScale = maxTotalAutonomy + (maxTotalAutonomy * 0.1);
    const maxStockageRatio = Math.max(...stockageRatio);
    const stockageRatioMaxScale = maxStockageRatio + (maxStockageRatio * 0.1);

    // ---------------- Main Charts ----------------

    // Chart 1: Global and Partial Fill Rate (Radar Chart)
    if (fillRateChart) {
      fillRateChart.data.labels = sites;
      fillRateChart.data.datasets[0].data = globalFillRate;
      fillRateChart.data.datasets[1].data = partialFillRate;
      fillRateChart.options.scales.r.max = fillRateMaxScale;
      fillRateChart.update();
    } else {
      const ctx = document.getElementById('fillRateChart').getContext('2d');
      fillRateChart = new Chart(ctx, {
        type: 'radar',
        data: {
          labels: sites,
          datasets: [
            { 
              label: 'Global Fill Rate (%)', 
              data: globalFillRate, 
              backgroundColor: 'rgba(75,192,192,0.4)', 
              borderColor: 'rgba(75,192,192,1)', 
              borderWidth: 2,
              pointBackgroundColor: 'rgba(75,192,192,1)',
              pointBorderColor: '#fff',
              pointHoverBackgroundColor: '#fff',
              pointHoverBorderColor: 'rgba(75,192,192,1)',
              datalabels: { display: false }
            },
            { 
              label: 'Partial Fill Rate (%)', 
              data: partialFillRate, 
              backgroundColor: 'rgba(255,159,64,0.4)', 
              borderColor: 'rgba(255,159,64,1)', 
              borderWidth: 2,
              pointBackgroundColor: 'rgba(255,159,64,1)',
              pointBorderColor: '#fff',
              pointHoverBackgroundColor: '#fff',
              pointHoverBorderColor: 'rgba(255,159,64,1)',
              datalabels: { display: false }
            }
          ]
        },
        options: {
          responsive: true,
          scales: {
            r: { 
              beginAtZero: true, 
              max: fillRateMaxScale, 
              pointLabels: { font: { size: 12 } },
              angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
              grid: { color: 'rgba(0, 0, 0, 0.1)' }
            }
          },
          plugins: {
            tooltip: {
              mode: 'index',
              intersect: false,
              callbacks: { label: context => `${context.dataset.label}: ${context.parsed.r.toFixed(1)}%` }
            },
            legend: {
              position: 'top',
              onClick: function (e, legendItem) {
                const index = legendItem.datasetIndex;
                const meta = this.chart.getDatasetMeta(index);
                meta.hidden = meta.hidden === null ? !this.chart.data.datasets[index].hidden : null;
                this.chart.update();
              }
            }
          }
        }
      });
    }

    // Chart 2: CAPEX Investment Cost per Site (Line Chart)
    if (investmentCostChart) {
      investmentCostChart.data.labels = selectedYears;
      investmentCostChart.data.datasets = capexDatasets;
      investmentCostChart.update();
    } else {
      const ctx = document.getElementById('investmentCostChart').getContext('2d');
      investmentCostChart = new Chart(ctx, {
        type: 'line',
        data: { labels: selectedYears, datasets: capexDatasets },
        options: {
          responsive: true,
          plugins: {
            datalabels: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(0,0,0,0.7)',
              callbacks: {
                title: context => 'Year: ' + context[0].label,
                label: context => {
                  let label = context.dataset.label || '';
                  if (label) label += ': ';
                  label += '$' + context.parsed.y.toFixed(1) + ' MM';
                  return label;
                }
              }
            },
            legend: {
              position: 'top',
              onClick: function (e, legendItem) {
                const index = legendItem.datasetIndex;
                const meta = this.chart.getDatasetMeta(index);
                meta.hidden = meta.hidden === null ? !this.chart.data.datasets[index].hidden : null;
                this.chart.update();
              }
            }
          },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Investment Cost (MM$)' } },
            x: { title: { display: true, text: 'Year' } }
          }
        }
      });
    }

    // Chart 3: Total and Partial Autonomy (Horizontal Stacked Bar Chart)
    if (totalAutonomyChart) {
      totalAutonomyChart.data.labels = sites;
      totalAutonomyChart.data.datasets[0].data = totalAutonomy;
      totalAutonomyChart.data.datasets[1].data = partialAutonomy;
      totalAutonomyChart.options.scales.x.max = autonomyMaxScale;
      totalAutonomyChart.update();
    } else {
      const ctx = document.getElementById('totalAutonomyChart').getContext('2d');
      totalAutonomyChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: sites,
          datasets: [
            {
              label: 'Total Autonomy (Years)',
              data: totalAutonomy,
              backgroundColor: 'rgba(54,162,235,0.6)',
              borderColor: 'rgba(54,162,235,1)',
              borderWidth: 1,
              datalabels: { display: false }
            },
            {
              label: 'Partial Autonomy (Years)',
              data: partialAutonomy,
              backgroundColor: 'rgba(255,99,132,0.6)',
              borderColor: 'rgba(255,99,132,1)',
              borderWidth: 1,
              datalabels: { display: false }
            }
          ]
        },
        options: {
          indexAxis: 'y', // Horizontal bars
          responsive: true,
          scales: {
            x: { 
              stacked: true, // Stacked bars
              beginAtZero: true, 
              max: autonomyMaxScale, 
              title: { display: true, text: 'Autonomy (Years)' } 
            },
            y: { 
              stacked: true, // Stacked bars
              title: { display: true, text: 'Sites' } 
            }
          },
          plugins: {
            legend: { position: 'top' },
            tooltip: { callbacks: { label: context => `${context.dataset.label}: ${context.parsed.x.toFixed(1)} yrs` } },
            datalabels: { display: false }
          }
        }
      });
    }

    // Chart 4: Stock Volume vs. Remaining Capacity (Stacked Bar Chart)
    if (stockVolumeChart) {
      stockVolumeChart.data.labels = sites;
      stockVolumeChart.data.datasets[0].data = stockVolume;
      stockVolumeChart.data.datasets[1].data = totalCapacity.map((cap, i) => cap - stockVolume[i]);
      stockVolumeChart.update();
    } else {
      const ctx = document.getElementById('stockVolumeChart').getContext('2d');
      stockVolumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: sites,
          datasets: [
            {
              label: 'Stock Volume (m³)',
              data: stockVolume,
              backgroundColor: 'rgba(255,99,132,0.6)', // Red color for stock volume
              borderColor: 'rgba(255,99,132,1)',
              borderWidth: 1,
              datalabels: { display: false }
            },
            {
              label: 'Remaining Capacity (m³)',
              data: totalCapacity.map((cap, i) => cap - stockVolume[i]),
              backgroundColor: 'rgba(54,162,235,0.6)', // Blue color for remaining capacity
              borderColor: 'rgba(54,162,235,1)',
              borderWidth: 1,
              datalabels: { display: false }
            }
          ]
        },
        options: {
          indexAxis: 'y', // Horizontal bars
          responsive: true,
          scales: {
            x: { 
              stacked: true, // Stacked bars
              beginAtZero: true, 
              title: { display: true, text: 'Volume (m³)' } 
            },
            y: { 
              stacked: true, // Stacked bars
              title: { display: true, text: 'Sites' } 
            }
          },
          plugins: {
            tooltip: { 
              mode: 'index', 
              intersect: false,
              callbacks: {
                label: context => {
                  const label = context.dataset.label || '';
                  const value = context.parsed.x;
                  return `${label}: ${value.toFixed(1)} m³`;
                }
              }
            },
            legend: {
              position: 'top',
              onClick: function (e, legendItem) {
                const index = legendItem.datasetIndex;
                const meta = this.chart.getDatasetMeta(index);
                meta.hidden = meta.hidden === null ? !this.chart.data.datasets[index].hidden : null;
                this.chart.update();
              }
            },
            datalabels: { display: false }
          }
        }
      });
    }

    // Chart 5: Stockage Ratio (Horizontal Bar Chart)
    if (stockageRatioChart) {
      stockageRatioChart.data.labels = sites;
      stockageRatioChart.data.datasets[0].data = stockageRatio;
      stockageRatioChart.options.scales.x.max = stockageRatioMaxScale;
      stockageRatioChart.update();
    } else {
      const ctx = document.getElementById('stockageRatioChart').getContext('2d');
      stockageRatioChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: sites,
          datasets: [
            {
              label: 'Stockage Ratio',
              data: stockageRatio,
              backgroundColor: 'rgba(75,192,192,0.6)',
              borderColor: 'rgba(75,192,192,1)',
              borderWidth: 1,
              hoverBackgroundColor: 'rgba(75,192,192,0.8)',
              datalabels: { display: false }
            }
          ]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          scales: {
            x: { beginAtZero: true, max: stockageRatioMaxScale, title: { display: true, text: 'Stockage Ratio' }, ticks: { stepSize: stockageRatioMaxScale / 5 } },
            y: { title: { display: true, text: 'Sites' }, ticks: { autoSkip: false } }
          },
          plugins: {
            tooltip: { callbacks: { label: context => `${context.dataset.label}: ${context.parsed.x.toFixed(1)}` } },
            legend: { display: false },
            datalabels: { display: false }
          }
        }
      });
    }

    // Chart 6: Total CAPEX per Site (Doughnut Chart with Values)
    if (capexTotalChart) {
      capexTotalChart.data.labels = sites;
      capexTotalChart.data.datasets[0].data = totalCapexData;
      capexTotalChart.update();
    } else {
      const ctx = document.getElementById('capexTotalChart').getContext('2d');
      capexTotalChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: sites,
          datasets: [{
            label: 'Total CAPEX (MM$)',
            data: totalCapexData,
            backgroundColor: sites.map((site, i) => getColor(i)),
            borderColor: sites.map((site, i) => getColor(i)),
            borderWidth: 1,
            datalabels: { 
              display: true,
              formatter: (value, context) => '$' + value.toFixed(1) + ' MM',
              color: '#000',
              font: { weight: 'bold' }
            }
          }]
        },
        options: {
          responsive: true,
          cutout: '50%',
          plugins: {
            legend: { position: 'top' },
            tooltip: { callbacks: { label: context => context.label + ': $' + context.parsed.toFixed(1) + ' MM' } },
            datalabels: { 
              display: true,
              formatter: (value, context) => '$' + value.toFixed(1) + ' MM',
              color: '#000',
              font: { weight: 'bold' }
            }
          }
        }
      });
    }
  }

  function clearCharts() {
    [fillRateChart, investmentCostChart, totalAutonomyChart,
     stockVolumeChart, stockageRatioChart, capexTotalChart].forEach(chart => {
      if (chart) chart.destroy();
    });
    fillRateChart = investmentCostChart = totalAutonomyChart = stockVolumeChart = stockageRatioChart = capexTotalChart = null;
  }

  socket.on('update_data', function (data) {
    console.log('Received data:', data);
    createOrUpdateCharts(data);
  });

  // Request initial update when page is loaded
  socket.emit('requestUpdate');
});