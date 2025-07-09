document.addEventListener('DOMContentLoaded', () => {
  // Show loading overlay
  const loadingOverlay = document.getElementById('loading');
  loadingOverlay.setAttribute('aria-hidden', 'false');

  try {
    // Update footer year
    document.getElementById('current-year').textContent = new Date().getFullYear();

    // Initialize all components
    initMap();
    initModal();
    initLightbox();
    initPrecipitationChart();
    initComponents();
  } catch (error) {
    console.error('Initialization error:', error);
    showError('An error occurred while initializing the application.');
  } finally {
    // Hide loading overlay after at least 1 second (for better UX)
    setTimeout(() => {
      loadingOverlay.setAttribute('aria-hidden', 'true');
    }, 1000);
  }

  // Initialize the Leaflet map
  function initMap() {
    // Site locations data
    const locations = [
      { name: "AGM", lat: 29.4662, lng: -8.7023, type: "Gold Mine" },
      { name: "BLEIDA flottation", lat: 30.3667, lng: -6.4349, type: "Processing Facility" },
      { name: "Hajjar", lat: 31.3755, lng: -8.0860, type: "Mine" },
      { name: "Ouansimi", lat: 29.2847, lng: -9.3749, type: "Mine" },
      { name: "BOU AZZER", lat: 30.5156, lng: -6.9162, type: "Cobalt Mine" },
      { name: "SMI", lat: 31.3361, lng: -5.7192, type: "Silver Mine" },
      { name: "TIZERT", lat: 30.2560, lng: -8.4571, type: "Copper Mine" },
      { name: "GGM", lat: 31.3848, lng: -8.0654, type: "Gold Mine" }
    ];

    // Create bounds covering all locations
    const bounds = L.latLngBounds(locations.map(loc => [loc.lat, loc.lng]));

    // Initialize map with custom options
    const map = L.map('map', {
      zoomControl: false,
      preferCanvas: true,
      fadeAnimation: true,
      zoomAnimation: true,
      attributionControl: false
    }).fitBounds(bounds, { padding: [50, 50] });

    // Add tile layer from Esri
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles © Esri',
        maxZoom: 19,
        errorTileUrl: '{{ url_for("static", filename="images/error-tile.png") }}'
      }
    ).addTo(map);

    // Add a custom-positioned attribution control
    L.control.attribution({
      position: 'bottomleft',
      prefix:
        '<a href="https://leafletjs.com/" target="_blank">Leaflet</a> | &copy; <a href="https://www.esri.com/" target="_blank">Esri</a>'
    }).addTo(map);

    // Map control event handlers
    document.getElementById('zoom-in').addEventListener('click', () => map.zoomIn());
    document.getElementById('zoom-out').addEventListener('click', () => map.zoomOut());
    document.getElementById('fit-bounds').addEventListener('click', () => {
      map.flyToBounds(bounds, { padding: [50, 50] });
    });
    document.getElementById('fullscreen').addEventListener('click', () => {
      const mapContainer = document.querySelector('.map-container');
      if (!document.fullscreenElement) {
        mapContainer.requestFullscreen().catch(err => {
          showError(`Error enabling fullscreen: ${err.message}`);
        });
      } else {
        document.exitFullscreen();
      }
    });

    // Custom marker icon
    const CustomIcon = L.DivIcon.extend({
      options: {
        html: '',
        className: 'custom-marker',
        iconSize: [32, 32]
      }
    });

    // Add markers for each location
    locations.forEach(loc => {
      const icon = new CustomIcon({ html: `<span>${loc.name.split(' ')[0]}</span>` });
      const marker = L.marker([loc.lat, loc.lng], {
        icon: icon,
        title: loc.name,
        alt: loc.name,
        riseOnHover: true
      }).addTo(map);

      // Bind tooltip to marker
      marker.bindTooltip(
        `<strong>${loc.name}</strong><br>${loc.type}`, {
          permanent: false,
          direction: 'top',
          className: 'map-tooltip',
          offset: [0, -20]
        }
      );

      // Bind popup with a modal trigger button
      marker.bindPopup(`
        <div class="popup-content">
          <h3 style="margin: 0 0 10px 0; color: var(--primary);">${loc.name}</h3>
          <p><strong>Type:</strong> ${loc.type}</p>
          <p><strong>Coordinates:</strong> ${loc.lat.toFixed(4)}, ${loc.lng.toFixed(4)}</p>
          <button class="view-details-btn" onclick="openModal('${loc.name}')">
            View Detailed Information
          </button>
        </div>
      `);

      // Also open modal on marker click
      marker.on('click', () => openModal(loc.name));
    });

    // Map error handling
    map.on('error', e => {
      console.error('Map error:', e.message);
      showError('Map loading failed. Please try again later.');
    });
  }

  // Initialize modal functionality
  function initModal() {
    const modal = document.getElementById('infoModal');
    const closeBtn = document.getElementById('closeModal');
    const modalOverlay = modal.querySelector('.modal-overlay');

    closeBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', closeModal);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') {
        closeModal();
      }
    });

    // Expose openModal globally
    window.openModal = openModal;
  }

  // Initialize lightbox for images
  function initLightbox() {
    const lightbox = document.getElementById('lightbox');
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxClose = lightbox.querySelector('.lightbox-close');

    lightboxClose.addEventListener('click', () => {
      lightbox.setAttribute('aria-hidden', 'true');
      lightbox.setAttribute('hidden', '');
    });
    lightbox.addEventListener('click', (e) => {
      if (e.target === lightbox) {
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.setAttribute('hidden', '');
      }
    });

    window.showLightbox = (src, alt) => {
      lightboxImage.src = src;
      lightboxImage.alt = alt || '';
      lightbox.removeAttribute('hidden');
      lightbox.setAttribute('aria-hidden', 'false');
    };

    // Delegate gallery image clicks to show lightbox
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('gallery-image')) {
        showLightbox(e.target.src, e.target.alt);
      }
    });
  }

  // Initialize the precipitation chart
  function initPrecipitationChart() {
    try {
      const data = [
        { annee: 2018, precipitation_mm: 420 },
        { annee: 2019, precipitation_mm: 380 },
        { annee: 2020, precipitation_mm: 450 },
        { annee: 2021, precipitation_mm: 390 },
        { annee: 2022, precipitation_mm: 410 },
        { annee: 2023, precipitation_mm: 430 }
      ];

      const ctx = document.getElementById('precipitationChart').getContext('2d');
      const years = data.map(item => item.annee);
      const precipitation = data.map(item => item.precipitation_mm);

      // Create a vertical gradient for the bars
      const gradient = ctx.createLinearGradient(0, 0, 0, 400);
      gradient.addColorStop(0, 'rgba(59, 130, 246, 0.8)');
      gradient.addColorStop(1, 'rgba(59, 130, 246, 0.2)');

      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: years,
          datasets: [{
            label: 'Precipitation (mm)',
            data: precipitation,
            backgroundColor: gradient,
            borderColor: 'rgba(59, 130, 246, 1)',
            borderWidth: 1,
            borderRadius: 4,
            hoverBackgroundColor: 'rgba(16, 185, 129, 0.7)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              enabled: true,
              mode: 'index',
              intersect: false,
              backgroundColor: 'var(--dark-700)',
              titleColor: 'var(--primary-light)',
              bodyColor: 'var(--text-primary)',
              borderColor: 'var(--primary)',
              borderWidth: 1,
              padding: 12,
              callbacks: {
                label: function(context) {
                  return ` ${context.dataset.label}: ${context.raw} mm`;
                }
              }
            },
            datalabels: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(255, 255, 255, 0.1)' },
              ticks: { color: 'var(--text-tertiary)' },
              title: { 
                display: true, 
                text: 'Precipitation (mm)', 
                color: 'var(--text-tertiary)',
                padding: { top: 10, bottom: 10 }
              }
            },
            x: {
              grid: { display: false },
              ticks: { color: 'var(--text-tertiary)' },
              title: { 
                display: true, 
                text: 'Year', 
                color: 'var(--text-tertiary)',
                padding: { top: 10, bottom: 10 }
              }
            }
          },
          animation: {
            duration: 1000,
            easing: 'easeOutQuart'
          }
        }
      });
    } catch (error) {
      console.error('Chart initialization error:', error);
      showError('Failed to load climate data visualization');
      document.getElementById('precipitationChart').style.display = 'none';
    }
  }

  // Initialize other components
  function initComponents() {
    // Add click handlers for feature items in the modal
    document.querySelectorAll('.feature-item').forEach(item => {
      item.addEventListener('click', function() {
        const featureKey = this.getAttribute('data-feature');
        updateFeatureContent(featureKey);
      });
    });

    // Example: Style any tables with the "data-table" class
    document.querySelectorAll('.data-table').forEach(table => {
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
      table.style.marginTop = 'var(--space-4)';
      table.querySelectorAll('th').forEach(th => {
        th.style.backgroundColor = 'var(--primary-dark)';
        th.style.color = 'white';
        th.style.padding = 'var(--space-2) var(--space-4)';
        th.style.textAlign = 'left';
      });
      table.querySelectorAll('td').forEach(td => {
        td.style.padding = 'var(--space-2) var(--space-4)';
        td.style.borderBottom = '1px solid var(--text-tertiary)';
      });
      table.querySelectorAll('tr').forEach((tr, index) => {
        tr.style.backgroundColor = index % 2 === 0 ? 'var(--dark-700)' : 'var(--dark-600)';
        tr.addEventListener('mouseenter', function() {
          this.style.backgroundColor = 'var(--primary)';
          this.style.color = 'white';
        });
        tr.addEventListener('mouseleave', function() {
          this.style.backgroundColor = index % 2 === 0 ? 'var(--dark-700)' : 'var(--dark-600)';
          this.style.color = 'var(--text-primary)';
        });
      });
    });
  }

  // Error message display routine
  function showError(message) {
    const existingError = document.querySelector('.error-message');
    if (existingError) {
      existingError.remove();
    }

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.style.position = 'fixed';
    errorDiv.style.bottom = '20px';
    errorDiv.style.left = '50%';
    errorDiv.style.transform = 'translateX(-50%)';
    errorDiv.style.backgroundColor = 'var(--error)';
    errorDiv.style.color = 'white';
    errorDiv.style.padding = 'var(--space-3) var(--space-4)';
    errorDiv.style.borderRadius = 'var(--radius-md)';
    errorDiv.style.boxShadow = 'var(--shadow-lg)';
    errorDiv.style.zIndex = '9999';
    errorDiv.style.display = 'flex';
    errorDiv.style.alignItems = 'center';
    errorDiv.style.gap = 'var(--space-2)';
    errorDiv.innerHTML = `
      <i class="fas fa-exclamation-circle"></i>
      <span>${message}</span>
    `;
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'assertive');

    document.body.appendChild(errorDiv);

    setTimeout(() => {
      errorDiv.style.opacity = '0';
      setTimeout(() => { errorDiv.remove(); }, 300);
    }, 5000);
  }

  // Fullscreen change handler: update the fullscreen toggle icon/label accordingly
  document.addEventListener('fullscreenchange', () => {
    const fullscreenBtn = document.getElementById('fullscreen');
    if (document.fullscreenElement) {
      fullscreenBtn.innerHTML = '<i class="fas fa-compress map-control-icon"></i>';
      fullscreenBtn.setAttribute('aria-label', 'Exit fullscreen');
    } else {
      fullscreenBtn.innerHTML = '<i class="fas fa-expand map-control-icon"></i>';
      fullscreenBtn.setAttribute('aria-label', 'Toggle fullscreen');
    }
  });

  /*****************************************************************
   * SITE DATA AND MODAL FUNCTIONALITY
   *****************************************************************/
  // Comprehensive site data
  const siteData = {
    "AGM": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='AGM Water Source Map' style='width:100%'></div>",
        "explanatory": "The water source for AGM comes from nearby wells and seasonal rainfall. The system was upgraded in 2022 to increase capacity by 30%.",
        "data": "Average daily water intake: 8,500 m³/day<br>Peak capacity: 12,000 m³/day<br>Source: 3 groundwater wells + surface collection",
        "graphs": "<div class='chart-container' style='height:200px;'><canvas id='agmWaterChart'></canvas></div>",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='AGM Water Source 1' class='gallery-image'><img src='static/images/water_source2.jpg' alt='AGM Water Source 2' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 29.4665, Longitude -8.7020",
        "explanatory": "Dewatering operations at AGM focus on maintaining safe working conditions in underground mines while minimizing environmental impact. The system includes:<br><br>- 5 main dewatering pumps<br>- 12 km of drainage channels<br>- 3 sedimentation ponds",
        "photos": "<div class='image-gallery'><img src='static/images/dewatering1.jpg' alt='AGM Dewatering System' class='gallery-image'><img src='static/images/dewatering2.jpg' alt='AGM Pump Station' class='gallery-image'></div>"
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Elevated drainage channels (8km total)<br>- Emergency overflow basins (3 locations)<br>- Real-time water level monitoring system",
        "explanatory": "AGM has implemented comprehensive flood protection measures due to its location in a region prone to seasonal flash floods. The system is designed to handle 1-in-100-year flood events with redundant safety measures.",
        "photos": "<div class='image-gallery'><img src='static/images/flood1.jpeg' alt='AGM Flood Protection' class='gallery-image'><img src='static/images/flood2.jpeg' alt='AGM Drainage System' class='gallery-image'><img src='static/images/flood3.jpeg' alt='AGM Overflow Basin' class='gallery-image'></div>"
      },
      "processWater": {
        "report": "Water Management Report (2023):<br><br>- Closed-loop water system efficiency: 85%<br>- Freshwater intake reduced by 35% since 2020<br>- Advanced filtration systems installed in Q2 2022",
        "photos": "<div class='image-gallery'><img src='static/images/process1.jpg' alt='AGM Water Processing' class='gallery-image'><img src='static/images/process2.jpg' alt='AGM Filtration System' class='gallery-image'></div>"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings (June 2024):<br>- pH: 7.4<br>- Turbidity: 3 NTU<br>- Heavy metals: Below detectable limits<br>- Conductivity: 450 µS/cm",
        "explanatory": "AGM maintains rigorous water quality standards with automated monitoring stations throughout the site. Key features include:<br><br>- 12 continuous monitoring stations<br>- Real-time alerts for parameter deviations<br>- Monthly comprehensive lab analysis",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='agmQualityChart'></canvas></div>"
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 85%<br>- Process water recycling: 92%<br>- Non-process applications: 65%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='agmReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Fire Protection Infrastructure:<br>- 15 fire hydrants installed<br>- 4 water reservoirs (total capacity: 1,200 m³)<br>- 2 dedicated fire trucks<br>- Annual fire drill compliance: 100%",
        "explanatory": "Fire protection at AGM meets international standards with regular drills and equipment maintenance. The system includes specialized foam suppression for chemical storage areas."
      },
      "climaticContext": {
        "information": "Climate Data (10-year averages):<br>- Annual rainfall: 380mm<br>- Temperature range: 18°C to 35°C<br>- Dry season: May to September<br>- Wet season: October to April",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='agmClimateChart'></canvas></div>"
      }
    },
    "BLEIDA flottation": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='BLEIDA Water Source Map' style='width:100%'></div>",
        "explanatory": "BLEIDA's flotation plant sources water from a combination of groundwater and treated municipal supply. The water quality is carefully controlled for optimal flotation performance.",
        "data": "Average daily water intake: 5,200 m³/day<br>Source ratio: 60% groundwater, 40% municipal",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='BLEIDA Water Source' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 30.3670, Longitude -6.4345",
        "explanatory": "Specialized dewatering systems handle the unique requirements of the flotation process, including chemical treatment of discharged water."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Reinforced containment walls<br>- Rapid drainage pumps (3 units)<br>- Chemical spill containment systems",
        "explanatory": "The flotation plant has specific flood protection needs due to chemical storage areas. The system is designed to prevent contamination during flood events."
      },
      "processWater": {
        "report": "Process Water Report:<br>- Water chemistry is carefully controlled for optimal flotation performance<br>- pH maintained at 8.1 ± 0.2<br>- Daily quality checks at 6 control points"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 8.1<br>- Turbidity: 8 NTU<br>- Chemical oxygen demand: 45 mg/L",
        "explanatory": "Continuous monitoring ensures process efficiency and environmental compliance at the flotation plant."
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 75%<br>- Process water recycling: 82%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='bleidaReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- Special chemical fire suppression systems installed<br>- 8 fire hydrants<br>- Monthly equipment checks"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 320mm<br>- Temperature range: 12°C to 28°C"
      }
    },
    "Hajjar": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='Hajjar Water Source Map' style='width:100%'></div>",
        "explanatory": "Hajjar mine utilizes a deep aquifer system with limited recharge capacity. Water conservation measures are strictly enforced.",
        "data": "Average daily water intake: 2,800 m³/day<br>Source: 2 deep aquifer wells",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='Hajjar Water Source' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 31.3758, Longitude -8.0855",
        "explanatory": "Dewatering is critical for maintaining stable pit walls and safe working conditions. The system includes 4 main pump stations."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Diversion channels (5km total)<br>- Emergency storage ponds (2 locations)<br>- Slope stabilization measures",
        "explanatory": "The mine's location makes it vulnerable to flash floods during rare rain events. Protection focuses on diverting water away from active mining areas."
      },
      "processWater": {
        "report": "Water Conservation Report:<br>- Water conservation measures have reduced consumption by 25% since 2020<br>- Implementation of dry stacking for tailings"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 7.8<br>- Turbidity: 12 NTU<br>- Total dissolved solids: 650 mg/L",
        "explanatory": "Monitoring focuses on potential impacts from pit dewatering on local groundwater quality."
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 65%<br>- Main reuse applications: Dust suppression, equipment washing"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- 8 fire hydrants installed<br>- 2 water trucks available<br>- Quarterly fire drills"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 280mm<br>- Temperature range: 10°C to 32°C"
      }
    },
    "Ouansimi": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='Ouansimi Water Source Map' style='width:100%'></div>",
        "explanatory": "Ouansimi relies on seasonal water sources supplemented by groundwater during dry periods. The system is designed for minimal environmental impact.",
        "data": "Average daily water intake: 1,800 m³/day<br>Source: Seasonal stream + 1 groundwater well",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='Ouansimi Water Source' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Dewatering system coordinates: Latitude 29.2850, Longitude -9.3745",
        "explanatory": "Limited dewatering requirements due to the mine's geology and small scale operations."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Basic drainage improvements<br>- Slope monitoring system",
        "explanatory": "Flood risk is relatively low but requires monitoring due to the site's proximity to a seasonal watercourse."
      },
      "processWater": {
        "report": "Water Management Report:<br>- Simple water treatment meets operational needs<br>- Monthly quality checks"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 7.1<br>- Turbidity: 6 NTU<br>- Heavy metals: Below detection limits"
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 50%<br>- Main reuse application: Equipment washing"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- Basic fire protection measures in place<br>- 4 fire extinguishers<br>- Annual safety training"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 350mm<br>- Temperature range: 15°C to 30°C"
      }
    },
    "BOU AZZER": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='BOU AZZER Water Source Map' style='width:100%'></div>",
        "explanatory": "BOU AZZER's cobalt processing requires high-quality water sources with strict chemical parameters. The water treatment system includes advanced filtration.",
        "data": "Average daily water intake: 6,200 m³/day<br>Source: 4 deep wells with iron removal systems",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='BOU AZZER Water Source' class='gallery-image'><img src='static/images/water_source2.jpg' alt='BOU AZZER Treatment Plant' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 30.5160, Longitude -6.9158",
        "explanatory": "Complex dewatering system handles both mine and processing plant requirements, with separate circuits for clean and process water."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Comprehensive containment system for process chemicals<br>- Elevated process areas<br>- Emergency shutoff valves",
        "explanatory": "Flood protection focuses on preventing contamination from process areas, with multiple containment barriers."
      },
      "processWater": {
        "report": "Process Water Report:<br>- Advanced water treatment ensures cobalt recovery efficiency<br>- Automated pH control system<br>- Daily quality monitoring at 8 points"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 6.9<br>- Turbidity: 2 NTU<br>- Cobalt: <0.01 mg/L<br>- Nickel: 0.05 mg/L",
        "explanatory": "Extensive monitoring network tracks water quality throughout the process chain and in discharge water."
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 90%<br>- Process water recycling: 95%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='bouazzerReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- Specialized fire suppression for cobalt processing areas<br>- 12 fire hydrants<br>- Foam suppression system"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 250mm<br>- Temperature range: 8°C to 38°C"
      }
    },
    "SMI": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='SMI Water Source Map' style='width:100%'></div>",
        "explanatory": "SMI's silver processing requires ultra-pure water for optimal recovery rates. The water treatment system includes reverse osmosis filtration.",
        "data": "Average daily water intake: 4,800 m³/day<br>Source: Municipal supply + on-site treatment",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='SMI Water Source' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 31.3365, Longitude -5.7188",
        "explanatory": "Dewatering systems are designed to handle both mine and processing needs, with silver recovery from process water."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Silver concentrate storage elevated above flood levels<br>- Waterproof electrical systems<br>- Backup power supply",
        "explanatory": "Critical to protect high-value silver products from water damage during extreme weather events."
      },
      "processWater": {
        "report": "Process Water Report:<br>- Water quality is tightly controlled to maximize silver recovery<br>- Conductivity maintained below 50 µS/cm<br>- Daily quality control checks"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 7.0<br>- Turbidity: 1 NTU<br>- Silver: <0.005 mg/L<br>- Cyanide: <0.01 mg/L",
        "explanatory": "Continuous monitoring ensures process efficiency and environmental compliance at the silver processing plant."
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 88%<br>- Process water recycling: 92%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='smiReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- Special fire protection for silver refining areas<br>- 10 fire hydrants<br>- Chemical suppression systems"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 300mm<br>- Temperature range: 5°C to 35°C"
      }
    },
    "TIZERT": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='TIZERT Water Source Map' style='width:100%'></div>",
        "explanatory": "Le 15 mai 2024, le pompage de l'eau du forage G5 vers la mine de Tizert a été mis en service. Cet événement a eu lieu en présence du client, MAA (Métallurgie de l'Anti Atlas), ainsi que du maître d'ouvrage délégué, REMINEX. Le pompage se fait avec un débit de 30 m³/heure.",
        "data": "Données actuelles:<br>- Débit moyen: 12,345 m³/jour<br>- Sources: Forage G5 + 2 puits annexes<br>- Capacité de stockage: 25,000 m³",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='tizertWaterChart'></canvas></div>",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='TIZERT Source Eau 1' class='gallery-image'><img src='static/images/water_source2.jpg' alt='TIZERT Source Eau 2' class='gallery-image'><img src='static/images/water_source3.jpeg' alt='TIZERT Forage G5' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Coordonnées du système principal: Latitude 30.2565, Longitude -8.4568",
        "explanatory": "TIZERT's copper mine requires extensive dewatering to access deeper ore bodies. The system includes:<br><br>- 6 pompes principales<br>- 15 km de canalisations<br>- Système de traitement des eaux avant rejet",
        "photos": "<div class='image-gallery'><img src='static/images/dewatering1.jpg' alt='TIZERT Système de Déviation' class='gallery-image'><img src='static/images/dewatering2.jpg' alt='TIZERT Station de Pompage' class='gallery-image'></div>"
      },
      "floodProtection": {
        "solutions": "Solutions Implementées:<br>- Systèmes de digues<br>- Drainage amélioré<br>- Bassins de rétention d'urgence",
        "explanatory": "La gestion efficace des eaux pluviales revêt une importance cruciale dans le contexte minier, car elle influence non seulement la productivité opérationnelle, mais également les aspects environnementaux et sociaux de l'exploitation minière. Le plan de gestion des eaux pluviales est nécessaire pour contrôler les eaux de ruissellement provenant de la mine et des infrastructures associées, ainsi que pour empêcher toute eau contaminée de pénétrer dans les cours d'eau naturels.",
        "photos": "<div class='image-gallery'><img src='static/images/flood1.jpeg' alt='TIZERT Protection Contre les Inondations' class='gallery-image'><img src='static/images/flood2.jpeg' alt='TIZERT Système de Drainage' class='gallery-image'><img src='static/images/flood3.jpeg' alt='TIZERT Mesures Anti-Inondation' class='gallery-image'><img src='static/images/flood4.jpg' alt='TIZERT Infrastructure Anti-Inondation' class='gallery-image'><img src='static/images/flood5.jpeg' alt='TIZERT Prévention des Inondations' class='gallery-image'></div>"
      },
      "processWater": {
        "report": "Rapport de Gestion de l'Eau:<br><br>- Système en boucle fermée avec 85% de recyclage<br>- Nouveaux filtres installés en 2023<br>- Surveillance quotidienne de la qualité",
        "photos": "<div class='image-gallery'><img src='static/images/process1.jpg' alt='TIZERT Traitement de lEau' class='gallery-image'><img src='static/images/process2.jpg' alt='TIZERT Système de Filtration' class='gallery-image'></div>"
      },
      "waterQualityMonitoring": {
        "data": "Dernières Mesures (Juin 2024):<br>- pH: 7.2<br>- Turbidité: 5 NTU<br>- Cuivre: 0.02 mg/L<br>- Conductivité: 520 µS/cm",
        "explanatory": "Ce paragraphe traite de la pureté de l'eau et des techniques de surveillance à la mine de cuivre de TIZERT. Le système comprend:<br><br>- 10 stations de surveillance continues<br>- Alertes en temps réel<br>- Analyses mensuelles en laboratoire",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='tizertQualityChart'></canvas></div>"
      },
      "waterReuse": {
        "data": "Métriques de Réutilisation 2023:<br>- Efficacité globale: 60%<br>- Recyclage eau de procédé: 75%<br>- Applications non-procédé: 45%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='tizertReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Infrastructure de Protection Incendie:<br>- 10 bornes incendie installées<br>- 3 réservoirs dédiés (capacité totale: 900 m³)<br>- 2 véhicules incendie<br>- Exercices annuels: 100% conformité",
        "explanatory": "Ce paragraphe détaille les mesures et équipements de protection incendie en place à TIZERT, y compris les systèmes spécialisés pour les zones de stockage de produits chimiques."
      },
      "climaticContext": {
        "information": "Données Climatiques (Moyennes 10 ans):<br>- Précipitations annuelles: 450mm<br>- Plage de température: 15°C à 30°C<br>- Saison sèche: Mai à Septembre<br>- Saison humide: Octobre à Avril",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='tizertClimateChart'></canvas></div>",
        "photos": "<div class='image-gallery'><img src='static/images/precipitation1.png' alt='TIZERT Traitement de lEau' class='gallery-image'><img src='static/images/precipitation3.png' alt='TIZERT Traitement de lEau' class='gallery-image'><img src='static/images/precipitation2.png' alt='TIZERT Système de Filtration' class='gallery-image'></div>"
      }
    },
    "GGM": {
      "sourceWater": {
        "map": "<div class='feature-map'><img src='static/images/map-placeholder.jpg' alt='GGM Water Source Map' style='width:100%'></div>",
        "explanatory": "GGM's gold processing plant uses a combination of surface water and groundwater sources. The water treatment includes cyanide destruction systems.",
        "data": "Average daily water intake: 7,500 m³/day<br>Source ratio: 70% surface water, 30% groundwater",
        "photos": "<div class='image-gallery'><img src='static/images/water_source1.jpg' alt='GGM Water Source' class='gallery-image'></div>"
      },
      "dewatering": {
        "coordinates": "Main dewatering system coordinates: Latitude 31.3852, Longitude -8.0650",
        "explanatory": "Dewatering is critical for both open pit and underground operations, with separate systems for each area."
      },
      "floodProtection": {
        "solutions": "Implemented Solutions:<br>- Containment ponds for process water<br>- Emergency spillways<br>- Cyanide neutralization systems",
        "explanatory": "Flood protection focuses on preventing cyanide solution releases, with multiple containment barriers and emergency response plans."
      },
      "processWater": {
        "report": "Process Water Report:<br>- Water management is critical for gold leaching processes<br>- Cyanide levels strictly controlled<br>- Automated monitoring systems"
      },
      "waterQualityMonitoring": {
        "data": "Latest Readings:<br>- pH: 10.2<br>- Turbidity: 4 NTU<br>- Cyanide: <0.05 mg/L<br>- Mercury: <0.001 mg/L",
        "explanatory": "Extensive monitoring ensures process control and environmental safety at the gold processing plant."
      },
      "waterReuse": {
        "data": "2023 Water Reuse Metrics:<br>- Overall efficiency: 92%<br>- Process water recycling: 95%",
        "graphs": "<div class='chart-container' style='height:250px;'><canvas id='ggmReuseChart'></canvas></div>"
      },
      "fireProtection": {
        "data": "Fire Protection:<br>- Special fire protection for gold refining areas<br>- 15 fire hydrants<br>- Foam suppression systems"
      },
      "climaticContext": {
        "information": "Climate Data:<br>- Annual rainfall: 350mm<br>- Temperature range: 12°C to 33°C"
      }
    }
  };

  // Current site variable
  let currentSite = "TIZERT";

  /**
   * Opens the modal with site information
   * @param {string} siteName - Name of the site to display
   */
  function openModal(siteName) {
    currentSite = siteName;
    const modal = document.getElementById('infoModal');
    const modalTitle = document.getElementById('modal-title');

    // Update modal title
    modalTitle.innerHTML = `<i class="fas fa-info-circle modal-title-icon"></i> ${siteName} - Site Details`;

    // Reset feature details
    document.getElementById('siteDetailsContent').innerHTML = `
      <p>Select a feature to view detailed information about ${siteName}.</p>
      <div class="feature-section">
        <h4 class="feature-section-title"><i class="fas fa-info-circle feature-section-icon"></i> Site Overview</h4>
        <p class="feature-text">${siteData[siteName]?.generalOverview || 'No general overview available for this site.'}</p>
      </div>
    `;

    // Show modal
    modal.setAttribute('aria-hidden', 'false');
    modal.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';
  }

  /**
   * Closes the modal
   */
  function closeModal() {
    const modal = document.getElementById('infoModal');
    modal.setAttribute('aria-hidden', 'true');
    modal.setAttribute('hidden', '');
    document.body.style.overflow = '';
  }

    /**
   * Updates the feature content in the modal
   * @param {string} featureKey - Key of the feature to display
   */
    function updateFeatureContent(featureKey) {
      const site = siteData[currentSite];
      if (!site || !site[featureKey]) {
        document.getElementById('siteDetailsContent').innerHTML = `
          <div class="feature-section">
            <h4 class="feature-section-title">
              <i class="${document.querySelector(`[data-feature="${featureKey}"] .feature-icon`).className} feature-section-icon"></i>
              ${document.querySelector(`[data-feature="${featureKey}"] .feature-label`).textContent}
            </h4>
            <p>No data available for this feature at ${currentSite}.</p>
          </div>
        `;
        return;
      }
  
      const feature = site[featureKey];
      let contentHTML = `
        <div class="feature-section">
          <h4 class="feature-section-title">
            <i class="${document.querySelector(`[data-feature="${featureKey}"] .feature-icon`).className} feature-section-icon"></i>
            ${document.querySelector(`[data-feature="${featureKey}"] .feature-label`).textContent}
          </h4>
      `;
  
      // Append explanatory text if available
      if (feature.explanatory) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-align-left feature-section-icon"></i> Description</h5>
            <p class="feature-text">${feature.explanatory.replace(/\n/g, '<br>')}</p>
          </div>
        `;
      }
  
      // Append data section if available
      if (feature.data) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-database feature-section-icon"></i> Data</h5>
            <div class="feature-data">${feature.data.replace(/\n/g, '<br>')}</div>
          </div>
        `;
      }
  
      // Append map section if available
      if (feature.map) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-map-marked-alt feature-section-icon"></i> Map</h5>
            ${feature.map}
          </div>
        `;
      }
  
      // Append charts section if available
      if (feature.graphs) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-chart-line feature-section-icon"></i> Charts</h5>
            ${feature.graphs}
          </div>
        `;
      }
  
      // Append photos section if available
      if (feature.photos) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-camera feature-section-icon"></i> Photos</h5>
            ${feature.photos}
          </div>
        `;
      }
  
      // Append solutions section if available
      if (feature.solutions) {
        contentHTML += `
          <div class="feature-section">
            <h5 class="feature-section-title"><i class="fas fa-lightbulb feature-section-icon"></i> Solutions</h5>
            <div class="feature-data">${feature.solutions.replace(/\n/g, '<br>')}</div>
          </div>
        `;
      }
  
      contentHTML += `</div>`; // Close main feature-section container
  
      // Update the modal's details area with the constructed HTML
      document.getElementById('siteDetailsContent').innerHTML = contentHTML;
  
      // If the feature includes canvas elements for charts, initialize them
      if (feature.graphs && feature.graphs.includes('canvas')) {
        initFeatureCharts(currentSite, featureKey);
      }
    }
  
    /**
     * Initialize charts for a specific feature (placeholder for future expansion)
     * @param {string} siteName - The name of the current site
     * @param {string} featureKey - The feature for which to initialize charts
     */
    function initFeatureCharts(siteName, featureKey) {
      // Placeholder: Replace with actual chart initialization logic as needed.
      console.log(`Initializing charts for ${siteName} - ${featureKey}`);
    }
  });
  