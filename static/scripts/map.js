// static/scripts/map.js

// Wrap your code in an IIFE to avoid polluting the global namespace
(function() {
    // Ensure the Cesium object is available
    if (typeof Cesium !== 'undefined') {
        // Set the default access token for Cesium Ion
        Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI4ZmM0YmMwMC1kNThhLTQ5MzEtYjY3MS04YzRiZmY4MmI4ODkiLCJpZCI6Mjc5NzE2LCJpYXQiOjE3NDA2NjU2ODR9.3YuKRyxuXjOgNWjYclO9k5vYsQBRqqAAEDqgTiSdyuM'; // Replace with your actual access token

        // Initialize the Cesium Viewer
        const viewer = new Cesium.Viewer('managemMap', {
            terrainProvider: Cesium.createWorldTerrain(),
            animation: false,
            timeline: false,
            selectionIndicator: false,
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            sceneModePicker: false,
            navigationHelpButton: false,
            infoBox: true,
        });

        // Fly the camera to the region of interest (e.g., Morocco)
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(-7.0926, 31.7917, 1500000),
            duration: 2,
        });

        // Define an array of tailing system data
        const tailingSystems = [
            {
                name: "Tailing System 1",
                latitude: 31.7917,
                longitude: -7.0926,
                description: `
                    <h2>Tailing System 1</h2>
                    <p>Details about Tailing System 1.</p>
                `,
            },
            {
                name: "Tailing System 2",
                latitude: 32.0000,
                longitude: -6.8000,
                description: `
                    <h2>Tailing System 2</h2>
                    <p>Details about Tailing System 2.</p>
                `,
            },
            // Add more tailing systems as needed
        ];

        // Add markers for each tailing system
        tailingSystems.forEach((system) => {
            viewer.entities.add({
                name: system.name,
                position: Cesium.Cartesian3.fromDegrees(system.longitude, system.latitude),
                billboard: {
                    image: '/static/images/marker.png', // Adjust the path based on your project structure
                    width: 32,
                    height: 32,
                },
                description: system.description,
            });
        });

        // Optionally, adjust the imagery provider
        viewer.imageryLayers.removeAll(); // Remove default Bing Maps imagery

        // Load high-resolution imagery using Cesium Ion
        viewer.imageryLayers.addImageryProvider(new Cesium.IonImageryProvider({ assetId: 3 }));

        // Add Cesium OSM Buildings (Optional)
        viewer.scene.primitives.add(Cesium.createOsmBuildings());
    } else {
        console.error('Cesium library is not loaded.');
    }
})();
