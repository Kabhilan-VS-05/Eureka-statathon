// Global chart instances (charts removed from UI)
      window.charts = {};
      let refreshInterval;
      window.analyticsLoading = false;

      // Global variables
      let occupations = [];
      let filteredOccupations = [];
      let currentPage = 1;
      const recordsPerPage = 25;

      // JavaScript is running
      console.log("DEBUG: JavaScript loaded successfully!");
      
      // Update visible test
      const jsStatus = document.getElementById("jsStatus");
      if (jsStatus) {
        jsStatus.textContent = "JAVASCRIPT LOADED!";
        jsStatus.style.color = "green";
      }
      
      let currentHistoryOccupationTitle = "";
      let currentHistoryRows = [];
      let currentSearchTerm = "";
      let semanticSearchResults = [];
      let semanticSearchTimer = null;
      let semanticSearchRequestId = 0;
      let allAnalyticsHistory = [];
      let analyticsControlTimer = null;
      const charts = window.charts;

      // Move all modals to body immediately to prevent z-index backdrop issues
      document.querySelectorAll('.modal').forEach(modal => {
        document.body.appendChild(modal);
      });

      // Initialize dashboard on page load
      document.addEventListener("DOMContentLoaded", function () {
        console.log("DEBUG: DOMContentLoaded event fired");
        initializeDashboard();
      });

      // Fallback in case DOMContentLoaded already fired
      if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(initializeDashboard, 1);
      }

      function initializeDashboard() {
        console.log("DEBUG: initializeDashboard called");
        initializeCharts();
        console.log("DEBUG: Charts initialized");
        loadOccupations();
        console.log("DEBUG: loadOccupations called");
        loadAnalyticsData();
        console.log("DEBUG: loadAnalyticsData called");
        updateLastUpdateTime();
        setInterval(updateLastUpdateTime, 1000);
        console.log("DEBUG: updateLastUpdateTime ticking in real time");

        startAnalyticsAutoRefresh();
      }

      function startAnalyticsAutoRefresh() {
        if (refreshInterval) {
          clearInterval(refreshInterval);
          refreshInterval = null;
        }

        refreshInterval = setInterval(() => {
          const analyticsTab = document.getElementById('analytics-tab');
          const ncoTab = document.getElementById('nco-analysis-tab');
          if (analyticsTab?.classList.contains('active')) {
            loadAnalyticsData();
          } else if (ncoTab?.classList.contains('active')) {
            loadNcoAnalysisData();
          }
        }, 30000);
      }

      // Loading functions
      function showLoading() {
        document.getElementById('loadingOverlay').style.display = 'flex';
      }

      function hideLoading() {
        document.getElementById('loadingOverlay').style.display = 'none';
      }

      // Data loading functions
      function loadOccupations() {
        showLoading();
        console.log("DEBUG: Starting to load occupations...");
        
        // Update visible test
        const jsStatus = document.getElementById("jsStatus");
        if (jsStatus) {
          jsStatus.textContent = "LOADING DATA...";
          jsStatus.style.color = "orange";
        }
        
        fetch("/admin/api/occupations")
          .then((response) => {
            console.log("DEBUG: Response received:", response.status);
            return response.json();
          })
          .then((data) => {
            console.log("DEBUG: Data received:", data.length, "records");
            occupations = Array.isArray(data) ? data : [];
            filteredOccupations = [...occupations];
            console.log("DEBUG: occupations array set to:", occupations.length);
            console.log("DEBUG: filteredOccupations array set to:", filteredOccupations.length);
            
            // Update visible test with success
            const jsStatus = document.getElementById("jsStatus");
            if (jsStatus) {
              jsStatus.textContent = `DATA LOADED: ${occupations.length} records`;
              jsStatus.style.color = "green";
            }
            
            updateStatistics();
            console.log("DEBUG: Statistics updated");
            updateFilters();
            console.log("DEBUG: Filters updated");
            displayTable();
            console.log("DEBUG: Table displayed");
            updateChartsData();
            console.log("DEBUG: Charts updated");
            if (allAnalyticsHistory.length) {
              updateSearchAnalyticsCharts(allAnalyticsHistory);
            }
            if (document.getElementById('nco-analysis-tab') && document.getElementById('nco-analysis-tab').classList.contains('active')) {
              refreshNcoFilterOptions();
              updateNcoAnalysisMetrics();
              drawNcoBubbleChart();
            }
          })
          .catch((error) => {
            console.error("Error loading occupations:", error);
            
            // Update visible test with error
            const jsStatus = document.getElementById("jsStatus");
            if (jsStatus) {
              jsStatus.textContent = `ERROR: ${error.message}`;
              jsStatus.style.color = "red";
            }
            
            showNotification("Failed to load occupations data", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      function loadNcoAnalysisData() {
        if (occupations.length === 0) {
          loadOccupations();
        }
        loadAnalyticsData();
      }

      function updateStatistics() {
        console.log("DEBUG: updateStatistics called with", occupations.length, "occupations");
        
        // Add null checks for elements that might not exist
        const totalOccupationsEl = document.getElementById("totalOccupations");
        console.log("DEBUG: totalOccupations element found:", !!totalOccupationsEl);
        if (totalOccupationsEl) {
          totalOccupationsEl.textContent = occupations.length.toLocaleString();
          console.log("DEBUG: Set totalOccupations to:", occupations.length);
        }

        const divisions = new Set(occupations.map((occ) => occ.division).filter((d) => d));
        console.log("DEBUG: Found divisions:", Array.from(divisions));
        const totalDivisionsEl = document.getElementById("totalDivisions");
        console.log("DEBUG: totalDivisions element found:", !!totalDivisionsEl);
        if (totalDivisionsEl) {
          totalDivisionsEl.textContent = divisions.size.toLocaleString();
          console.log("DEBUG: Set totalDivisions to:", divisions.size);
        }

        const families = new Set(occupations.map((occ) => occ.family).filter((f) => f));
        console.log("DEBUG: Found families count:", families.size);
        const totalFamiliesEl = document.getElementById("totalFamilies");
        console.log("DEBUG: totalFamilies element found:", !!totalFamiliesEl);
        if (totalFamiliesEl) {
          totalFamiliesEl.textContent = families.size.toLocaleString();
          console.log("DEBUG: Set totalFamilies to:", families.size);
        }

        // Calculate data completeness
        const totalFields = occupations.length * 8; // Approximate fields per record
        const filledFields = occupations.reduce((count, occ) => {
          return count + [
            occ.occupation_title,
            occ.nco_code,
            occ.division,
            occ.family,
            occ.description,
            occ.nco_2004_code
          ].filter(field => field && field.trim()).length;
        }, 0);
        const completeness = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;
        const dataCompletenessEl = document.getElementById("dataCompleteness");
        if (dataCompletenessEl) {
          dataCompletenessEl.textContent = completeness + '%';
        }
      }

      
      // Chart initialization - Create all 6 Chart.js instances
      function initializeCharts() {
        console.log("DEBUG: initializeCharts called");
        
        // 1. Search Volume Trend Chart
        const ctxVolume = document.getElementById('searchVolumeTrendChart');
        if (ctxVolume && !charts.searchVolumeTrendChart) {
          charts.searchVolumeTrendChart = new Chart(ctxVolume, {
            type: 'line',
            data: {
              labels: [],
              datasets: [{
                label: 'Searches',
                data: [],
                borderColor: '#0b3d91',
                backgroundColor: 'rgba(11, 61, 145, 0.05)',
                borderWidth: 2,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#0b3d91',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                x: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 2. Top 10 Searches Chart
        const ctxTopSearches = document.getElementById('topSearchesChart');
        if (ctxTopSearches && !charts.topSearchesChart) {
          charts.topSearchesChart = new Chart(ctxTopSearches, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Search Count',
                data: [],
                backgroundColor: '#f97316',
                borderColor: '#ea580c',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 3. Search Success Rate Chart replaced by D3 Sunburst chart

        // 4. Language Distribution Chart
        const ctxLanguage = document.getElementById('languageDistributionChart');
        if (ctxLanguage && !charts.languageDistributionChart) {
          charts.languageDistributionChart = new Chart(ctxLanguage, {
            type: 'pie',
            data: {
              labels: [],
              datasets: [{
                data: [],
                backgroundColor: [
                  '#1e3a8a', '#3b82f6', '#60a5fa', '#93c5fd', '#dbeafe',
                  '#f97316', '#fed7aa', '#10b981', '#6ee7b7', '#a7f3d0'
                ],
                borderColor: '#fff',
                borderWidth: 2
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { position: 'bottom', labels: { color: '#6b7280' } }
              }
            }
          });
        }

        // 5. Top 10 Occupations Chart
        const ctxOccupations = document.getElementById('topOccupationsChart');
        if (ctxOccupations && !charts.topOccupationsChart) {
          charts.topOccupationsChart = new Chart(ctxOccupations, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Found Count',
                data: [],
                backgroundColor: '#3b82f6',
                borderColor: '#1e40af',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        // 6. NCO Division Demand Chart
        const ctxConfidence = document.getElementById('confidenceTrendChart');
        if (ctxConfidence && !charts.confidenceTrendChart) {
          charts.confidenceTrendChart = new Chart(ctxConfidence, {
            type: 'bar',
            data: {
              labels: [],
              datasets: [{
                label: 'Search Matches',
                data: [],
                backgroundColor: '#10b981',
                borderColor: '#047857',
                borderWidth: 1
              }]
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: { display: false }
              },
              scales: {
                x: {
                  beginAtZero: true,
                  ticks: { stepSize: 1, color: '#6b7280' },
                  grid: { color: '#e5e7eb' }
                },
                y: {
                  ticks: { color: '#6b7280' },
                  grid: { display: false }
                }
              }
            }
          });
        }

        console.log("DEBUG: All 6 charts initialized successfully");
      }

      function updateChartsData() {
        return;
      }

      function updateSearchAnalyticsCharts(historyData) {
        if (!Array.isArray(historyData)) {
          console.warn("Invalid history data");
          return;
        }

        allAnalyticsHistory = historyData;

        if (historyData.length > 0) {
          const dates = historyData.map(entry => parseAnalyticsDate(entry.ts)).filter(Boolean);
          if (dates.length > 0) {
            const minDate = new Date(Math.min(...dates));
            const maxDate = new Date();
            
            const minDateStr = minDate.toISOString().split('T')[0];
            const maxDateStr = maxDate.toISOString().split('T')[0];
            
            const startInput = document.getElementById("analyticsStartDate");
            const endInput = document.getElementById("analyticsEndDate");
            
            if (startInput) {
              startInput.min = minDateStr;
              startInput.max = maxDateStr;
              if (!startInput.value) startInput.value = minDateStr;
            }
            if (endInput) {
              endInput.min = minDateStr;
              endInput.max = maxDateStr;
              if (!endInput.value) endInput.value = maxDateStr;
            }
          }
        }

        populateAnalyticsFilterOptions();
        const filteredHistory = getFilteredAnalyticsHistory(historyData);
        
        // Calculate max range based on available distinct values
        const uniqueQueries = new Set(filteredHistory.map(entry => entry.query).filter(Boolean)).size;
        const uniqueOccups = new Set(filteredHistory.map(entry => entry.occupation_title).filter(Boolean)).size;
        const uniqueDivs = new Set(filteredHistory.map(entry => getAnalyticsEntryProperty(entry, 'division')).filter(Boolean)).size;
        
        // Set dynamic max limit for the slider based on the data length
        const maxRange = Math.max(5, uniqueQueries, uniqueOccups, uniqueDivs);
        
        const topNInput = document.getElementById("analyticsTopN");
        if (topNInput) {
          topNInput.max = maxRange;
          // Enforce bounds immediately if current value exceeds new max
          if (parseInt(topNInput.value, 10) > maxRange) {
            topNInput.value = maxRange;
          }
          const valEl = document.getElementById("analyticsTopNValue");
          if (valEl) valEl.textContent = topNInput.value;
        }

        const topN = getAnalyticsTopN();
        const groupBy = document.getElementById("analyticsGroupBy")?.value || "day";

        console.log("DEBUG: Updating charts with", filteredHistory.length, "filtered history entries");

        updateAnalyticsMetricTiles(filteredHistory);

        // ===== CHART 1: Search Volume Trend =====
        const trendCounts = countByTimeBucket(filteredHistory, groupBy);
        const trendEntries = Object.entries(trendCounts);

        if (charts.searchVolumeTrendChart) {
          charts.searchVolumeTrendChart.data.labels = trendEntries.map(([label]) => label);
          charts.searchVolumeTrendChart.data.datasets[0].data = trendEntries.map(([, count]) => count);
          charts.searchVolumeTrendChart.update();
        }
        setTextContent("searchVolumeTrendTitle", `Search Volume Trend by ${capitalize(groupBy)}`);

        // ===== CHART 2: Top Search Queries =====
        const topSearches = topCounts(filteredHistory, (entry) => entry.query, topN);

        if (charts.topSearchesChart) {
          charts.topSearchesChart.data.labels = topSearches.map(([query]) => truncateLabel(query, 35));
          charts.topSearchesChart.data.datasets[0].data = topSearches.map(([, count]) => count);
          charts.topSearchesChart.update();
        }
        setTextContent("topSearchesTitle", `Top ${topN} Search Queries`);

        // ===== CHART 3: NCO Search Demand Sunburst =====
        drawNcoSearchDemandSunburst(filteredHistory);

        // ===== CHART 4: Translation Usage =====
        const languageCounts = {};
        filteredHistory.forEach(entry => {
          let langName = entry.detected_language;
          if (!langName) {
            if (entry.was_translated) {
              langName = "Tamil";
            } else {
              langName = "English";
            }
          }
          if (langName === "en" || langName === "English") langName = "English";
          
          languageCounts[langName] = (languageCounts[langName] || 0) + 1;
        });

        const languageColors = {
          "English": "#5dade2",      // Soft Sapphire Blue
          "Tamil": "#ec7063",        // Pastel Coral / Rose
          "Hindi": "#f4d03f",        // Pastel Gold
          "Telugu": "#eb984e",       // Pastel Orange
          "Bengali": "#af7ac5",      // Pastel Amethyst
          "Marathi": "#52be80",      // Sage Green
          "Gujarati": "#a569bd",     // Pastel Orchid
          "Kannada": "#48c9b0",      // Pastel Mint
          "Malayalam": "#58d68d",    // Pastel Light Green
          "Punjabi": "#f5b041",      // Pastel Amber
          "Urdu": "#85c1e9",         // Pastel Sky Blue
          "Other": "#cbd5e1"         // Soft Gray
        };

        if (charts.languageDistributionChart) {
          const labels = Object.keys(languageCounts);
          const data = Object.values(languageCounts);
          const bgColors = labels.map(lang => languageColors[lang] || languageColors["Other"]);
          
          charts.languageDistributionChart.data.labels = labels;
          charts.languageDistributionChart.data.datasets[0].data = data;
          charts.languageDistributionChart.data.datasets[0].backgroundColor = bgColors;
          charts.languageDistributionChart.update();
        }

        // ===== CHART 5: Top Matched Occupations =====
        const topOccupations = topCounts(filteredHistory, (entry) => entry.occupation_title, topN);

        if (charts.topOccupationsChart) {
          charts.topOccupationsChart.data.labels = topOccupations.map(([title]) => truncateLabel(title, 35));
          charts.topOccupationsChart.data.datasets[0].data = topOccupations.map(([, count]) => count);
          charts.topOccupationsChart.update();
        }
        setTextContent("topOccupationsTitle", `Top ${topN} Matched Occupations`);

        // ===== CHART 6: NCO Division Demand =====
        const topDivisions = topCounts(filteredHistory, (entry) => getAnalyticsEntryProperty(entry, 'division'), topN);

        if (charts.confidenceTrendChart) {
          charts.confidenceTrendChart.data.labels = topDivisions.map(([division]) => truncateLabel(division, 35));
          charts.confidenceTrendChart.data.datasets[0].data = topDivisions.map(([, count]) => count);
          charts.confidenceTrendChart.update();
        }

        // Update last update time
        updateLastUpdateTime();
      }

      function drawNcoSearchDemandSunburst(historyData) {
        const container = document.getElementById("sunburstChartContainer");
        if (!container) return;

        // 1. Clear previous chart
        d3.select(container).selectAll("*").remove();

        // 2. Build hierarchical data (now including 4 levels: Division -> Sub-Division -> Group -> Family)
        const rootData = { name: "NCO", children: [] };
        
        historyData.forEach(entry => {
          const div = getAnalyticsEntryProperty(entry, "division");
          const sub = getAnalyticsEntryProperty(entry, "sub_division");
          const grp = getAnalyticsEntryProperty(entry, "group");
          const fam = getAnalyticsEntryProperty(entry, "family");

          if (!div) return;

          // Find/create Division
          let divNode = rootData.children.find(c => c.name === div);
          if (!divNode) {
            divNode = { name: div, children: [] };
            rootData.children.push(divNode);
          }

          if (!sub) return;

          // Find/create Sub-Division
          let subNode = divNode.children.find(c => c.name === sub);
          if (!subNode) {
            subNode = { name: sub, children: [] };
            divNode.children.push(subNode);
          }

          if (!grp) return;

          // Find/create Group
          let grpNode = subNode.children.find(c => c.name === grp);
          if (!grpNode) {
            grpNode = { name: grp, children: [] };
            subNode.children.push(grpNode);
          }

          if (!fam) return;

          // Find/create Family
          let famNode = grpNode.children.find(c => c.name === fam);
          if (!famNode) {
            famNode = { name: fam, value: 0 };
            grpNode.children.push(famNode);
          }

          famNode.value += 1;
        });

        // If there are no valid children, display "No Data" message
        if (rootData.children.length === 0) {
          d3.select(container).append("div")
            .style("color", "#94a3b8")
            .style("font-size", "14px")
            .style("font-style", "italic")
            .text("No NCO-mapped queries found in history.");
          return;
        }

        // 3. Set up dimensions
        const width = container.clientWidth || 280;
        const height = container.clientHeight || 280;
        const radius = Math.min(width, height) / 2;

        // 4. Create SVG
        const svg = d3.select(container)
          .append("svg")
          .attr("width", width)
          .attr("height", height)
          .append("g")
          .attr("transform", `translate(${width / 2}, ${height / 2})`);

        // 5. Partition layout
        const hierarchy = d3.hierarchy(rootData)
          .sum(d => d.value)
          .sort((a, b) => b.value - a.value);

        const partition = d3.partition()
          .size([2 * Math.PI, radius]);

        const root = partition(hierarchy);

        // 6. Arc generator - spacing between slices (angular) and rings (concentric radial)
        const centerRadius = 40;
        const ringWidth = (radius - centerRadius) / 4;

        const arc = d3.arc()
          .startAngle(d => d.x0)
          .endAngle(d => d.x1)
          .padAngle(d => 0.015)
          .padRadius(radius / 2)
          .innerRadius(d => centerRadius + (d.depth - 1) * ringWidth + 2.5)
          .outerRadius(d => centerRadius + d.depth * ringWidth - 2.5);

        // 7. Colors: Curated premium palette based on the NCO division with progressive brightness per level
        const divisionColors = {
          "Managers": "#5dade2",            // Soft Sapphire Blue
          "Professionals": "#af7ac5",       // Soft Amethyst Purple
          "Technicians and Associate Professionals": "#48c9b0", // Soft Teal / Mint
          "Clerks/Clerical Support Workers": "#52be80", // Sage Green
          "Service and Sales Workers": "#f4d03f",       // Pale Amber / Gold
          "Skilled Agricultural, Forestry and Fishery Workers": "#eb984e", // Soft Orange / Apricot
          "Craft and Related Trades Workers": "#ec7063", // Soft Coral / Rose
          "Plant and Machine Operators, and Assemblers": "#a569bd", // Soft Orchid
          "Elementary Occupations": "#a6acaf" // Soft Silver / Gray
        };

        function getNodeColor(d) {
          if (d.depth === 0) return "#ffffff";
          
          let p = d;
          while (p.depth > 1) {
            p = p.parent;
          }
          const divisionName = p.data.name;
          const hexColor = divisionColors[divisionName] || ncoColorScale(divisionName) || "#cbd5e1";
          const baseColor = d3.color(hexColor);
          
          if (d.depth === 1) {
            return baseColor.toString();
          } else if (d.depth === 2) {
            return baseColor.brighter(0.22).toString();
          } else if (d.depth === 3) {
            return baseColor.brighter(0.44).toString();
          } else if (d.depth === 4) {
            return baseColor.brighter(0.66).toString();
          }
          return baseColor.toString();
        }

        // 8. Render paths
        const paths = svg.selectAll("path")
          .data(root.descendants().filter(d => d.depth > 0))
          .enter()
          .append("path")
          .attr("d", arc)
          .style("fill", d => getNodeColor(d))
          .style("stroke", "#ffffff")
          .style("stroke-width", "1px")
          .style("cursor", "pointer")
          .style("transition", "opacity 0.2s ease");

        // 9. Tooltip and hovering logic
        const tooltip = d3.select("#sunburstTooltip");
        const activeInfo = document.getElementById("sunburstActiveInfo");

        paths.on("mouseover", function(event, d) {
          paths.style("opacity", 0.35);
          
          const ancestorsNodes = [];
          let current = d;
          while (current.depth > 0) {
            ancestorsNodes.push(current);
            current = current.parent;
          }
          paths.filter(node => ancestorsNodes.includes(node))
            .style("opacity", 1.0)
            .style("stroke", "#334155")
            .style("stroke-width", "1.5px");

          const totalSearches = root.value || 1;
          const share = ((d.value / totalSearches) * 100).toFixed(1);
          
          let levelLabel = "Division";
          if (d.depth === 2) levelLabel = "Sub-Division";
          if (d.depth === 3) levelLabel = "Group";
          if (d.depth === 4) levelLabel = "Family";

          const meta = lookupNcoHierarchyMeta(
            d.data.name, 
            d.depth === 1 ? 'division' : 
            d.depth === 2 ? 'sub_division' : 
            d.depth === 3 ? 'group' : 'family'
          );
          const codePrefix = meta && meta.code ? `[Code ${meta.code}] ` : "";

          // Show floating tooltip
          tooltip.style("opacity", 1)
            .html(`
              <div style="font-weight: 700; font-size: 13px; color: #f8fafc; margin-bottom: 2px;">
                ${codePrefix}${d.data.name}
              </div>
              <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-bottom: 6px;">
                ${levelLabel}
              </div>
              <div style="font-size: 13px; font-weight: 600; color: #38bdf8; border-top: 1px solid #334155; padding-top: 4px;">
                ${d.value.toLocaleString()} search${d.value === 1 ? "" : "es"} (${share}%)
              </div>
            `);
            
          // Update details inside the activeInfo div outside the chart
          let displayName = d.data.name;
          if (displayName.includes(":")) {
            displayName = displayName.split(":").slice(1).join(":").trim();
          }

          if (activeInfo) {
            activeInfo.innerHTML = `<span style="color: #475569; font-weight: 700;">${levelLabel}:</span> <span style="color: #0b3d91; font-weight: 600;">${displayName}</span>`;
          }

          // Update number inside the circle center
          d3.select(".sunburst-center-value")
            .style("font-size", "18px")
            .text(d.value.toLocaleString());
        })
        .on("mousemove", function(event) {
          const cardRect = container.getBoundingClientRect();
          const tooltipWidth = tooltip.node().offsetWidth || 180;
          const tooltipHeight = tooltip.node().offsetHeight || 80;
          
          // Default: position to the bottom-right of cursor
          let xPos = event.clientX - cardRect.left + 15;
          let yPos = event.clientY - cardRect.top + 15;
          
          // If it overflows right, show on left of cursor
          if (xPos + tooltipWidth > cardRect.width - 10) {
            xPos = event.clientX - cardRect.left - tooltipWidth - 15;
          }
          // If it overflows bottom, show above cursor
          if (yPos + tooltipHeight > cardRect.height - 10) {
            yPos = event.clientY - cardRect.top - tooltipHeight - 15;
          }

          // Strict boundary clamping so tooltip NEVER overflows the card borders
          xPos = Math.max(8, Math.min(cardRect.width - tooltipWidth - 8, xPos));
          yPos = Math.max(8, Math.min(cardRect.height - tooltipHeight - 8, yPos));

          tooltip
            .style("left", xPos + "px")
            .style("top", yPos + "px");
        })
        .on("mouseleave", function() {
          paths.style("opacity", 1.0)
            .style("stroke", "#ffffff")
            .style("stroke-width", "1px");
          
          tooltip.style("opacity", 0);

          if (activeInfo) {
            activeInfo.textContent = "Hover over a segment to view NCO classification details";
          }

          d3.select(".sunburst-center-value")
            .style("font-size", "18px")
            .text(root.value.toLocaleString());
        });

        // 10. Draw center circle display
        svg.append("circle")
          .attr("r", centerRadius + 2) // slightly overlap pad gap
          .style("fill", "#ffffff")
          .style("stroke", "#e2e8f0")
          .style("stroke-width", "1px")
          .style("pointer-events", "none");

        const centerTextG = svg.append("g")
          .attr("pointer-events", "none");

        centerTextG.append("text")
          .attr("class", "sunburst-center-value")
          .attr("y", 6) // Perfectly centered
          .attr("text-anchor", "middle")
          .style("font-size", "18px")
          .style("font-weight", "800")
          .style("fill", "#0f172a")
          .style("font-family", "Arial, sans-serif")
          .text(root.value.toLocaleString());
      }

      function applyAnalyticsControls() {
        clearTimeout(analyticsControlTimer);
        analyticsControlTimer = setTimeout(() => {
          updateSearchAnalyticsCharts(allAnalyticsHistory);
        }, 120);
      }

      function resetAnalyticsControls() {
        setControlValue("analyticsDateRange", "all");
        setControlValue("analyticsStartDate", "");
        setControlValue("analyticsEndDate", "");
        setControlValue("analyticsGroupBy", "day");
        setControlValue("analyticsQueryFilter", "");
        setControlValue("analyticsOccupationFilter", "");
        setControlValue("analyticsDivisionFilter", "");
        setControlValue("analyticsSubDivisionFilter", "");
        setControlValue("analyticsGroupFilter", "");
        setControlValue("analyticsOutcomeFilter", "");
        setControlValue("analyticsTopN", "10");
        updateSearchAnalyticsCharts(allAnalyticsHistory);
      }

      function getFilteredAnalyticsHistory(historyData) {
        const dateRange = document.getElementById("analyticsDateRange")?.value || "all";
        const dateWindow = getAnalyticsDateWindow(dateRange);
        const queryFilter = (document.getElementById("analyticsQueryFilter")?.value || "").trim().toLowerCase();
        const occupationFilter = document.getElementById("analyticsOccupationFilter")?.value || "";
        const divisionFilter = document.getElementById("analyticsDivisionFilter")?.value || "";
        const subDivisionFilter = document.getElementById("analyticsSubDivisionFilter")?.value || "";
        const groupFilter = document.getElementById("analyticsGroupFilter")?.value || "";
        const outcomeFilter = document.getElementById("analyticsOutcomeFilter")?.value || "";

        return historyData.filter((entry) => {
          const entryDate = parseAnalyticsDate(entry.ts);
          if (!entryDate) return false;
          if (dateWindow.start && entryDate < dateWindow.start) return false;
          if (dateWindow.end && entryDate > dateWindow.end) return false;
          if (queryFilter && !`${entry.query || ""} ${entry.translated_query || ""}`.toLowerCase().includes(queryFilter)) return false;
          if (occupationFilter && (entry.occupation_title || "") !== occupationFilter) return false;
          if (divisionFilter && getAnalyticsEntryProperty(entry, 'division') !== divisionFilter) return false;
          if (subDivisionFilter && getAnalyticsEntryProperty(entry, 'sub_division') !== subDivisionFilter) return false;
          if (groupFilter && getAnalyticsEntryProperty(entry, 'group') !== groupFilter) return false;
          if (outcomeFilter === "success" && !isSuccessfulAnalyticsEntry(entry)) return false;
          if (outcomeFilter === "empty" && isSuccessfulAnalyticsEntry(entry)) return false;
          if (outcomeFilter === "translated" && !entry.was_translated) return false;
          if (outcomeFilter === "original" && entry.was_translated) return false;
          return true;
        });
      }

      function getAnalyticsDateWindow(dateRange) {
        if (dateRange === "all") return { start: null, end: null };

        if (dateRange === "custom") {
          const startValue = document.getElementById("analyticsStartDate")?.value;
          const endValue = document.getElementById("analyticsEndDate")?.value;
          const start = startValue ? new Date(`${startValue}T00:00:00`) : null;
          const end = endValue ? new Date(`${endValue}T23:59:59`) : null;
          return { start, end };
        }

        const days = parseInt(dateRange, 10) || 7;
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - (days - 1));
        start.setHours(0, 0, 0, 0);
        end.setHours(23, 59, 59, 999);
        return { start, end };
      }

      function populateAnalyticsFilterOptions() {
        populateAnalyticsSelect(
          "analyticsOccupationFilter",
          "All occupations",
          [...new Set(allAnalyticsHistory.map((entry) => entry.occupation_title).filter(Boolean))].sort()
        );

        const divisions = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'division'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsDivisionFilter", "All divisions", divisions);

        const subDivisions = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'sub_division'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsSubDivisionFilter", "All sub-divisions", subDivisions);

        const groups = [...new Set(
          allAnalyticsHistory
            .map((entry) => getAnalyticsEntryProperty(entry, 'group'))
            .filter(Boolean)
        )].sort();
        populateAnalyticsSelect("analyticsGroupFilter", "All groups", groups);
      }

      function populateAnalyticsSelect(selectId, allLabel, values) {
        const select = document.getElementById(selectId);
        if (!select) return;
        const currentValue = select.value;
        select.innerHTML = "";
        select.appendChild(new Option(allLabel, ""));
        values.forEach((value) => select.appendChild(new Option(value, value)));
        if (values.includes(currentValue)) {
          select.value = currentValue;
        }
      }

      function updateAnalyticsMetricTiles(filteredHistory) {
        const total = filteredHistory.length;
        const successCount = filteredHistory.filter(isSuccessfulAnalyticsEntry).length;
        const translatedCount = filteredHistory.filter((entry) => entry.was_translated).length;
        const uniqueOccupations = new Set(filteredHistory.map((entry) => entry.occupation_title).filter(Boolean)).size;

        setTextContent("analyticsMetricSearches", total.toLocaleString());
        setTextContent("analyticsMetricSuccess", total ? `${((successCount / total) * 100).toFixed(1)}%` : "0%");
        setTextContent("analyticsMetricTranslated", total ? `${((translatedCount / total) * 100).toFixed(1)}%` : "0%");
        setTextContent("analyticsMetricOccupations", uniqueOccupations.toLocaleString());
      }

      function countByTimeBucket(historyData, groupBy) {
        const counts = {};
        historyData
          .slice()
          .sort((a, b) => parseAnalyticsDate(a.ts) - parseAnalyticsDate(b.ts))
          .forEach((entry) => {
            const date = parseAnalyticsDate(entry.ts);
            if (!date) return;
            const label = getTimeBucketLabel(date, groupBy);
            counts[label] = (counts[label] || 0) + 1;
          });
        return counts;
      }

      function getTimeBucketLabel(date, groupBy) {
        if (groupBy === "month") {
          return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
        }
        if (groupBy === "week") {
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay());
          return weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }

      function topCounts(items, selector, limit) {
        const counts = {};
        items.forEach((item) => {
          const value = selector(item);
          if (!value) return;
          counts[value] = (counts[value] || 0) + 1;
        });
        return Object.entries(counts)
          .sort(([, a], [, b]) => b - a)
          .slice(0, limit);
      }

      function normalizeCodeForCompare(code) {
        if (!code) return "";
        return String(code).trim().toLowerCase();
      }

      function getAnalyticsEntryProperty(entry, propName) {
        const code = normalizeCodeForCompare(entry.nco_code || "");
        const matchedOccupation = occupations.find((occupation) =>
          normalizeCodeForCompare(occupation.nco_code) === code
        );
        return matchedOccupation ? matchedOccupation[propName] : "";
      }

      function isSuccessfulAnalyticsEntry(entry) {
        if (typeof entry.returned_count === "number") return entry.returned_count > 0;
        return Boolean(entry.occupation_title || entry.nco_code);
      }

      function parseAnalyticsDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? null : date;
      }

      function getAnalyticsTopN() {
        const input = document.getElementById("analyticsTopN");
        const value = parseInt(input?.value || "10", 10);
        const max = parseInt(input?.max || "20", 10);
        return Math.max(3, Math.min(value || 10, max));
      }

      function truncateLabel(value, length) {
        const text = String(value || "");
        return text.length > length ? `${text.slice(0, length)}...` : text;
      }

      function setTextContent(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
      }

      function setControlValue(id, value) {
        const element = document.getElementById(id);
        if (element) element.value = value;
      }

      function capitalize(value) {
        const text = String(value || "");
        return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
      }

      // Table functions
      function updateFilters() {
        refreshSearchFilterOptions();
        if (typeof refreshNcoFilterOptions === 'function') {
          refreshNcoFilterOptions();
        }
      }

      function getSearchFilterValues() {
        return {
          division: getMultiSelectValues("divisionFilter"),
          sub_division: getMultiSelectValues("subDivisionFilter"),
          group: getMultiSelectValues("groupFilter"),
          family: getMultiSelectValues("familyFilter"),
        };
      }

      function occupationMatchesSearchFilters(occupation, filters, skipField = "") {
        return Object.entries(filters).every(([field, values]) => {
          if (!values.length || field === skipField) return true;
          return values.includes(occupation[field] || "");
        });
      }

      function populateSearchFilter(selectId, allLabel, field, filters, changedId = "") {
        const root = document.getElementById(selectId);
        if (!root) return;
        const menu = root.querySelector(".multi-select-menu");
        if (!menu) return;

        const currentValues = getMultiSelectValues(selectId);
        menu.innerHTML = `
          <div class="multi-select-clear" onclick="resetMultiSelect('${selectId}')" style="padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #e5e7eb; color: #475569; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; background: #f8fafc; transition: background 0.2s ease;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
            <i class="fas fa-undo"></i> Reset Filter
          </div>
        `;

        const values = [...new Set(
          occupations
            .filter((occ) => occupationMatchesSearchFilters(occ, filters, field))
            .map((occ) => occ[field])
            .filter(Boolean)
        )].sort();

        values.forEach((value, index) => {
          const optionId = `${selectId}-${index}`;
          const label = document.createElement("label");
          label.className = "multi-select-option";
          label.innerHTML = `
            <input type="checkbox" id="${optionId}" value="${escapeHtml(value)}" ${currentValues.includes(value) ? "checked" : ""} onchange="handleMultiSelectChange('${selectId}')" />
            <span>${escapeHtml(value)}</span>
          `;
          menu.appendChild(label);
        });

        if (selectId !== changedId) {
          const validSelections = currentValues.filter((value) => values.includes(value));
          setMultiSelectValues(selectId, validSelections);
        }
        updateMultiSelectDisplay(selectId, allLabel);
      }

      function refreshSearchFilterOptions(changedId = "") {
        const filters = getSearchFilterValues();
        populateSearchFilter("divisionFilter", "All Divisions", "division", filters, changedId);
        populateSearchFilter("subDivisionFilter", "All Sub Divisions", "sub_division", filters, changedId);
        populateSearchFilter("groupFilter", "All Groups", "group", filters, changedId);
        populateSearchFilter("familyFilter", "All Families", "family", filters, changedId);
      }

      function updateSearchSubDivisionFilter() {
        refreshSearchFilterOptions("divisionFilter");
      }

      function updateSearchGroupFilter() {
        refreshSearchFilterOptions("subDivisionFilter");
      }

      function updateSearchFamilyFilter() {
        refreshSearchFilterOptions("groupFilter");
      }

      function toggleMultiSelect(selectId) {
        const root = document.getElementById(selectId);
        if (!root) return;
        document.querySelectorAll(".multi-select.open").forEach((select) => {
          if (select.id !== selectId) select.classList.remove("open");
        });
        root.classList.toggle("open");
      }

      function getMultiSelectValues(selectId) {
        const root = document.getElementById(selectId);
        if (!root) return [];
        return Array.from(root.querySelectorAll(".multi-select-menu input:checked"))
          .map((input) => input.value);
      }

      function setMultiSelectValues(selectId, values) {
        const selectedValues = new Set(values);
        const root = document.getElementById(selectId);
        if (!root) return;
        root.querySelectorAll(".multi-select-menu input").forEach((input) => {
          input.checked = selectedValues.has(input.value);
        });
      }

      function updateMultiSelectDisplay(selectId, allLabel) {
        const root = document.getElementById(selectId);
        const display = root?.querySelector(".multi-select-display");
        if (!display) return;
        const values = getMultiSelectValues(selectId);
        if (!values.length) {
          display.textContent = allLabel;
        } else if (values.length === 1) {
          display.textContent = values[0];
        } else {
          display.textContent = `${values.length} selected`;
        }
      }

      function handleMultiSelectChange(selectId) {
        if (selectId.startsWith("nco")) {
          const ncoLabelMap = {
            ncoDivisionFilter: "All Divisions",
            ncoSubDivisionFilter: "All Sub Divisions",
            ncoGroupFilter: "All Groups",
            ncoFamilyFilter: "All Families",
          };
          updateMultiSelectDisplay(selectId, ncoLabelMap[selectId] || "All");
          refreshNcoFilterOptions(selectId);
          drawNcoBubbleChart();
          return;
        }

        const labelMap = {
          divisionFilter: "All Divisions",
          subDivisionFilter: "All Sub Divisions",
          groupFilter: "All Groups",
          familyFilter: "All Families",
        };
        updateMultiSelectDisplay(selectId, labelMap[selectId] || "All");
        refreshSearchFilterOptions(selectId);
        filterOccupations();
      }

      function resetMultiSelect(selectId) {
        setMultiSelectValues(selectId, []);
        handleMultiSelectChange(selectId);
      }

      function resetAllDatabaseFilters() {
        ['divisionFilter', 'subDivisionFilter', 'groupFilter', 'familyFilter'].forEach(id => {
          setMultiSelectValues(id, []);
          const labelMap = {
            divisionFilter: "All Divisions",
            subDivisionFilter: "All Sub Divisions",
            groupFilter: "All Groups",
            familyFilter: "All Families",
          };
          updateMultiSelectDisplay(id, labelMap[id]);
        });
        const searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.value = '';
        const searchMode = document.getElementById('adminSearchMode');
        if (searchMode) searchMode.value = 'normal';
        
        refreshSearchFilterOptions();
        if (searchMode && searchMode.value === 'semantic') {
          searchOccupations();
        } else {
          filterOccupations();
        }
      }

      function getNcoFilterValues() {
        return {
          division: getMultiSelectValues("ncoDivisionFilter"),
          sub_division: getMultiSelectValues("ncoSubDivisionFilter"),
          group: getMultiSelectValues("ncoGroupFilter"),
          family: getMultiSelectValues("ncoFamilyFilter"),
        };
      }

      function refreshNcoFilterOptions(changedId = "") {
        const filters = getNcoFilterValues();
        populateNcoSearchFilter("ncoDivisionFilter", "All Divisions", "division", filters, changedId);
        populateNcoSearchFilter("ncoSubDivisionFilter", "All Sub Divisions", "sub_division", filters, changedId);
        populateNcoSearchFilter("ncoGroupFilter", "All Groups", "group", filters, changedId);
        populateNcoSearchFilter("ncoFamilyFilter", "All Families", "family", filters, changedId);
      }

      function resetAllNcoFilters() {
        ['ncoDivisionFilter', 'ncoSubDivisionFilter', 'ncoGroupFilter', 'ncoFamilyFilter'].forEach(id => {
          setMultiSelectValues(id, []);
          const labelMap = {
            ncoDivisionFilter: "All Divisions",
            ncoSubDivisionFilter: "All Sub Divisions",
            ncoGroupFilter: "All Groups",
            ncoFamilyFilter: "All Families",
          };
          updateMultiSelectDisplay(id, labelMap[id]);
        });
        
        refreshNcoFilterOptions();
        drawNcoBubbleChart();
      }

      function escapeHtml(value) {
        return String(value || "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }

      function displayTable() {
        const tbody = document.getElementById("occupationsTableBody");
        if (!tbody) return;

        const start = (currentPage - 1) * recordsPerPage;
        const end = start + recordsPerPage;
        const pageData = filteredOccupations.slice(start, end);

        tbody.innerHTML = "";
        pageData.forEach((occupation) => {
          const row = document.createElement("tr");
          const ncoDisplay = occupation.nco_code
            ? `<span class="nco-code">${formatNcoCode(occupation.nco_code)}</span>`
            : `<span style="color:#9ca3af; font-style:italic;">No Code</span>`;
          row.innerHTML = `
            <td>${occupation.row_id}</td>
            <td>${escapeHtml(occupation.occupation_title)}</td>
            <td>${ncoDisplay}</td>
            <td>${escapeHtml(occupation.division || '—')}</td>
            <td>${escapeHtml(occupation.sub_division || '—')}</td>
            <td>${escapeHtml(occupation.group || '—')}</td>
            <td>${escapeHtml(occupation.family || '—')}</td>
            <td>
              <div class="action-buttons">
                <button type="button" class="action-btn edit" onclick="editOccupation(${occupation.row_id})" title="Edit">
                  <i class="fas fa-edit"></i>
                </button>
                <button type="button" class="action-btn history" onclick="showPromptHistory(${occupation.row_id})" title="View History">
                  <i class="fas fa-clock"></i>
                </button>
                <button type="button" class="action-btn delete" onclick="deleteOccupation(${occupation.row_id})" title="Delete">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </td>
          `;
          tbody.appendChild(row);
        });

        const recordCount = document.getElementById("recordCount");
        if (recordCount) {
          recordCount.textContent = `${filteredOccupations.length} records`;
        }

        updatePagination();
      }

      function updatePagination() {
        const totalPages = Math.ceil(filteredOccupations.length / recordsPerPage);
        const pagination = document.getElementById("pagination");
        if (!pagination) return;

        pagination.innerHTML = "";
        if (totalPages === 0) return;

        // Previous button
        const prevLi = document.createElement("li");
        prevLi.innerHTML = `<a class="page-link ${currentPage === 1 ? 'disabled' : ''}" href="#" onclick="changePage(${currentPage - 1})">Previous</a>`;
        pagination.appendChild(prevLi);

        // Page numbers
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
          const li = document.createElement("li");
          li.innerHTML = `<a class="page-link ${i === currentPage ? 'active' : ''}" href="#" onclick="changePage(${i})">${i}</a>`;
          pagination.appendChild(li);
        }

        // Next button
        const nextLi = document.createElement("li");
        nextLi.innerHTML = `<a class="page-link ${currentPage === totalPages ? 'disabled' : ''}" href="#" onclick="changePage(${currentPage + 1})">Next</a>`;
        pagination.appendChild(nextLi);
      }

      function changePage(page) {
        const totalPages = Math.ceil(filteredOccupations.length / recordsPerPage);
        if (page < 1 || page > totalPages) return;
        
        currentPage = page;
        displayTable();
      }

      // Search and filter functions
      function searchOccupations() {
        currentSearchTerm = document.getElementById("searchInput").value.trim();
        currentPage = 1;
        clearTimeout(semanticSearchTimer);
        const mode = getAdminSearchMode();
        if (mode === "semantic") {
          semanticSearchTimer = setTimeout(() => applyFilters(), 250);
          return;
        }
        applyFilters();
      }

      function applyFilters() {
        if (getAdminSearchMode() === "semantic" && currentSearchTerm) {
          runSemanticOccupationSearch(currentSearchTerm);
          return;
        }

        semanticSearchResults = [];
        setAdminSearchStatus("");
        applyOccupationFilters(occupations, true);
      }

      function applyOccupationFilters(sourceOccupations, includeTextSearch) {
        const filters = getSearchFilterValues();
        const searchTerm = (currentSearchTerm || "").toLowerCase();

        filteredOccupations = sourceOccupations.filter((occupation) => {
          const divisionMatch = !filters.division.length || filters.division.includes(occupation.division || "");
          const subDivisionMatch = !filters.sub_division.length || filters.sub_division.includes(occupation.sub_division || "");
          const groupMatch = !filters.group.length || filters.group.includes(occupation.group || "");
          const familyMatch = !filters.family.length || filters.family.includes(occupation.family || "");

          if (!includeTextSearch || !searchTerm) {
            return divisionMatch && subDivisionMatch && groupMatch && familyMatch;
          }

          const searchFields = [
            occupation.occupation_title,
            occupation.description,
            occupation.division,
            occupation.sub_division,
            occupation.group,
            occupation.family,
            occupation.nco_code,
            occupation.nco_2004_code
          ].filter(Boolean);
          
          const textMatch = searchFields.some(field => 
            field.toLowerCase().includes(searchTerm)
          );
          
          return textMatch && divisionMatch && subDivisionMatch && groupMatch && familyMatch;
        });

        currentPage = 1;
        displayTable();
      }

      function filterOccupations() {
        const evt = typeof event !== "undefined" ? event : null;
        const changedId = evt && evt.target ? evt.target.id : "";
        if (!evt || !evt.target || !evt.target.closest || !evt.target.closest(".multi-select-menu")) {
          refreshSearchFilterOptions(changedId);
        }

        currentPage = 1;
        if (getAdminSearchMode() === "semantic" && currentSearchTerm && semanticSearchResults.length) {
          applyOccupationFilters(semanticSearchResults, false);
          setAdminSearchStatus(`Showing ${filteredOccupations.length} filtered semantic matches`);
          return;
        }
        applyFilters();
      }

      function getAdminSearchMode() {
        const modeSelect = document.getElementById("adminSearchMode");
        return modeSelect ? modeSelect.value : "normal";
      }

      function setAdminSearchStatus(message) {
        const status = document.getElementById("adminSearchStatus");
        if (status) status.textContent = message || "";
      }

      function runSemanticOccupationSearch(query) {
        const requestId = ++semanticSearchRequestId;
        setAdminSearchStatus("Searching with Semantic search...");

        fetch("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            search_mode: "general",
            top_k: 100
          })
        })
          .then((response) => response.json())
          .then((data) => {
            if (requestId !== semanticSearchRequestId) return;
            if (data.error) {
              throw new Error(data.error);
            }

            const rankedResults = Array.isArray(data.results) ? data.results : [];
            const rankedOccupations = rankedResults
              .map((result) => {
                if (Number.isInteger(result.row_id)) {
                  return occupations.find((occupation) => occupation.row_id === result.row_id);
                }
                const resultCode = normalizeCodeForCompare(result.nco_code || result.nco_2015 || "");
                return occupations.find((occupation) => normalizeCodeForCompare(occupation.nco_code) === resultCode);
              })
              .filter(Boolean);

            semanticSearchResults = rankedOccupations;
            applyOccupationFilters(semanticSearchResults, false);
            setAdminSearchStatus(`Showing ${filteredOccupations.length} of ${rankedOccupations.length} semantic matches`);
          })
          .catch((error) => {
            if (requestId !== semanticSearchRequestId) return;
            console.error("Semantic admin search failed:", error);
            semanticSearchResults = [];
            filteredOccupations = [];
            displayTable();
            setAdminSearchStatus("Semantic search failed. Try normal table search.");
          });
      }

      function normalizeCodeForCompare(value) {
        return String(value || "").replace(/\s+/g, "").toLowerCase();
      }

      function refreshData() {
        loadOccupations();
        showNotification("Data refreshed successfully", "success");
      }

      // CRUD operations
      function editOccupation(rowId) {
        const occupation = occupations.find((occ) => occ.row_id === rowId);
        if (!occupation) return;

        // Populate basic fields
        document.getElementById("editRowId").value = occupation.row_id;
        document.getElementById("editTitle").value = occupation.occupation_title || "";
        document.getElementById("editAdminPassword").value = "";
        document.getElementById("editDescription").value = occupation.description || "";

        // Handle NCO code split
        const ncoCode = formatNcoCode(occupation.nco_code || "");
        const parts = ncoCode.split(".");
        if (parts.length === 2) {
          document.getElementById("editNcoCodeFirst").value = parts[0];
          document.getElementById("editNcoCodeSecond").value = parts[1];
        }

        const hasNco2004 = !!(occupation.nco_2004_code || "").trim();
        const editNco2004Row = document.getElementById("editNco2004Row");
        const editNco2004First = document.getElementById("editNco2004CodeFirst");
        const editNco2004Second = document.getElementById("editNco2004CodeSecond");
        if (hasNco2004) {
          const parts2004 = (occupation.nco_2004_code || "").split(".");
          editNco2004First.value = parts2004[0] || "";
          editNco2004Second.value = parts2004[1] || "";
          editNco2004First.disabled = false;
          editNco2004Second.disabled = false;
          editNco2004Row.style.display = "";
        } else {
          editNco2004First.value = "";
          editNco2004Second.value = "";
          editNco2004First.disabled = true;
          editNco2004Second.disabled = true;
          editNco2004Row.style.display = "none";
        }

        // Populate division/sub division/group/family dropdowns
        populateDivisionDropdowns();
        document.getElementById("editDivision").value = occupation.division || "";
        updateSubDivisionDropdown("editDivision", "editSubDivision");
        document.getElementById("editSubDivision").value = occupation.sub_division || "";
        updateGroupDropdown("editDivision", "editSubDivision", "editGroup");
        document.getElementById("editGroup").value = occupation.group || "";
        updateFamilyDropdown("editDivision", "editSubDivision", "editGroup", "editFamily");
        document.getElementById("editFamily").value = occupation.family || "";

        // Show modal using Bootstrap 5
        showModalById("editModal");
      }

      function buildNcoCode(firstId, secondId, expectedSecondLength) {
        const first = (document.getElementById(firstId).value || "").trim();
        const second = (document.getElementById(secondId).value || "").trim();
        if (!/^\d{4}$/.test(first)) {
          return { ok: false, error: "First segment must be exactly 4 digits" };
        }
        const secondRegex = new RegExp(`^\\d{${expectedSecondLength}}$`);
        if (!secondRegex.test(second)) {
          return { ok: false, error: `Second segment must be exactly ${expectedSecondLength} digits` };
        }
        return { ok: true, code: `${first}.${second}` };
      }

      function validateOccupationPayload(payload, requireNco2004) {
        if (!payload.occupation_title) return "Occupation title is required";
        if (!payload.division) return "Division is required";
        if (!payload.sub_division) return "Sub Division is required";
        if (!payload.group) return "Group is required";
        if (!payload.family) return "Family is required";
        if (!payload.description) return "Occupation description is required";
        if (!payload.admin_password) return "Admin password is required";
        if (!/^\d{4}\.\d{4}$/.test(payload.nco_code || "")) return "NCO 2015 must be in XXXX.XXXX format";
        if (requireNco2004 && !/^\d{4}\.\d{2}$/.test(payload.nco_2004_code || "")) return "NCO 2004 must be in XXXX.XX format";
        if (payload.nco_2004_code && !/^\d{4}\.\d{2}$/.test(payload.nco_2004_code)) return "NCO 2004 must be in XXXX.XX format";
        return "";
      }

      function saveOccupation() {
        const rowId = document.getElementById("editRowId").value;
        const nco2015 = buildNcoCode("editNcoCodeFirst", "editNcoCodeSecond", 4);
        if (!nco2015.ok) {
          showNotification(nco2015.error, "error");
          return;
        }
        const nco2004RowVisible = document.getElementById("editNco2004Row").style.display !== "none";
        let nco2004Code = "";
        if (nco2004RowVisible) {
          const nco2004 = buildNcoCode("editNco2004CodeFirst", "editNco2004CodeSecond", 2);
          if (!nco2004.ok) {
            showNotification(nco2004.error, "error");
            return;
          }
          nco2004Code = nco2004.code;
        }

        const data = {
          row_id: parseInt(rowId),
          occupation_title: (document.getElementById("editTitle").value || "").trim(),
          nco_code: nco2015.code,
          nco_2004_code: nco2004Code,
          description: (document.getElementById("editDescription").value || "").trim(),
          division: (document.getElementById("editDivision").value || "").trim(),
          sub_division: (document.getElementById("editSubDivision").value || "").trim(),
          group: (document.getElementById("editGroup").value || "").trim(),
          family: (document.getElementById("editFamily").value || "").trim(),
          admin_password: (document.getElementById("editAdminPassword").value || "").trim(),
        };
        const validationError = validateOccupationPayload(data, nco2004RowVisible);
        if (validationError) {
          showNotification(validationError, "error");
          return;
        }

        showLoading();
        fetch(`/admin/api/occupations/${rowId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              const editModal = bootstrap.Modal.getInstance(document.getElementById("editModal"));
              if (editModal) {
                editModal.hide();
              }
              loadOccupations();
              showNotification("Occupation updated successfully", "success");
            } else {
              showNotification(result.error || "Failed to update occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error updating occupation:", error);
            showNotification("Failed to update occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      function showAddModal() {
        document.getElementById("addForm").reset();
        populateDivisionDropdowns();
        document.getElementById("addSubDivision").innerHTML = '<option value="">Select Sub Division</option>';
        document.getElementById("addGroup").innerHTML = '<option value="">Select Group</option>';
        document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
        showModalById("addModal");
      }

      function cleanupStuckModalState() {
        document.body.classList.remove('modal-open');
        document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove());
        document.body.style.removeProperty('padding-right');
      }

      function showModalById(modalId) {
        cleanupStuckModalState();

        const modalEl = document.getElementById(modalId);
        if (!modalEl) return;

        // Ensure modal is a direct child of body to avoid z-index / stacking issues
        if (modalEl.parentElement !== document.body) {
          document.body.appendChild(modalEl);
        }

        // Ensure interactive layering
        modalEl.style.zIndex = '1055';

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl, {
          backdrop: true,
          keyboard: true,
          focus: true,
        });

        modalEl.addEventListener('hidden.bs.modal', cleanupStuckModalState, { once: true });
        modal.show();
      }

      // Helper functions for dropdowns
      function populateDivisionDropdowns() {
        const divisions = [...new Set(occupations.map((occ) => occ.division).filter((d) => d))];
        
        // Update edit modal division dropdown
        const editDivisionSelect = document.getElementById("editDivision");
        if (editDivisionSelect) {
          editDivisionSelect.innerHTML = '<option value="">Select Division</option>';
          divisions.forEach((division) => {
            editDivisionSelect.innerHTML += `<option value="${division}">${division}</option>`;
          });
        }
        
        // Update add modal division dropdown
        const addDivisionSelect = document.getElementById("addDivision");
        if (addDivisionSelect) {
          addDivisionSelect.innerHTML = '<option value="">Select Division</option>';
          divisions.forEach((division) => {
            addDivisionSelect.innerHTML += `<option value="${division}">${division}</option>`;
          });
        }
      }

      function updateSubDivisionDropdown(divisionSelectId, subDivisionSelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        if (!divisionSelect || !subDivisionSelect) return;
        const selectedDivision = divisionSelect.value;
        subDivisionSelect.innerHTML = '<option value="">Select Sub Division</option>';
        if (!selectedDivision) return;
        const subDivisions = [...new Set(
          occupations
            .filter((occ) => (occ.division || "") === selectedDivision)
            .map((occ) => occ.sub_division)
            .filter((s) => s)
        )];
        subDivisions.forEach((subDivision) => {
          subDivisionSelect.innerHTML += `<option value="${subDivision}">${subDivision}</option>`;
        });
      }

      function updateGroupDropdown(divisionSelectId, subDivisionSelectId, groupSelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        const groupSelect = document.getElementById(groupSelectId);
        if (!divisionSelect || !subDivisionSelect || !groupSelect) return;
        const selectedDivision = divisionSelect.value;
        const selectedSubDivision = subDivisionSelect.value;
        groupSelect.innerHTML = '<option value="">Select Group</option>';
        if (!selectedDivision || !selectedSubDivision) return;
        const groups = [...new Set(
          occupations
            .filter((occ) => (occ.division || "") === selectedDivision && (occ.sub_division || "") === selectedSubDivision)
            .map((occ) => occ.group)
            .filter((g) => g)
        )];
        groups.forEach((groupValue) => {
          groupSelect.innerHTML += `<option value="${groupValue}">${groupValue}</option>`;
        });
      }

      function updateFamilyDropdown(divisionSelectId, subDivisionSelectId, groupSelectId, familySelectId) {
        const divisionSelect = document.getElementById(divisionSelectId);
        const subDivisionSelect = document.getElementById(subDivisionSelectId);
        const groupSelect = document.getElementById(groupSelectId);
        const familySelect = document.getElementById(familySelectId);
        if (!divisionSelect || !subDivisionSelect || !groupSelect || !familySelect) return;
        const selectedDivision = divisionSelect.value;
        const selectedSubDivision = subDivisionSelect.value;
        const selectedGroup = groupSelect.value;
        familySelect.innerHTML = '<option value="">Select Family</option>';
        if (!selectedDivision || !selectedSubDivision || !selectedGroup) return;
        const families = [...new Set(
          occupations
            .filter((occ) =>
              (occ.division || "") === selectedDivision &&
              (occ.sub_division || "") === selectedSubDivision &&
              (occ.group || "") === selectedGroup
            )
            .map((occ) => occ.family)
            .filter((f) => f)
        )];
        families.forEach((family) => {
          familySelect.innerHTML += `<option value="${family}">${family}</option>`;
        });
      }

      // Add event listeners for division changes
      document.addEventListener("DOMContentLoaded", function() {
        // Edit modal division change
        const editDivisionSelect = document.getElementById("editDivision");
        if (editDivisionSelect) {
          editDivisionSelect.addEventListener("change", function() {
            updateSubDivisionDropdown("editDivision", "editSubDivision");
            document.getElementById("editGroup").innerHTML = '<option value="">Select Group</option>';
            document.getElementById("editFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const editSubDivisionSelect = document.getElementById("editSubDivision");
        if (editSubDivisionSelect) {
          editSubDivisionSelect.addEventListener("change", function() {
            updateGroupDropdown("editDivision", "editSubDivision", "editGroup");
            document.getElementById("editFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const editGroupSelect = document.getElementById("editGroup");
        if (editGroupSelect) {
          editGroupSelect.addEventListener("change", function() {
            updateFamilyDropdown("editDivision", "editSubDivision", "editGroup", "editFamily");
          });
        }

        const addDivisionSelect = document.getElementById("addDivision");
        if (addDivisionSelect) {
          addDivisionSelect.addEventListener("change", function() {
            updateSubDivisionDropdown("addDivision", "addSubDivision");
            document.getElementById("addGroup").innerHTML = '<option value="">Select Group</option>';
            document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const addSubDivisionSelect = document.getElementById("addSubDivision");
        if (addSubDivisionSelect) {
          addSubDivisionSelect.addEventListener("change", function() {
            updateGroupDropdown("addDivision", "addSubDivision", "addGroup");
            document.getElementById("addFamily").innerHTML = '<option value="">Select Family</option>';
          });
        }
        const addGroupSelect = document.getElementById("addGroup");
        if (addGroupSelect) {
          addGroupSelect.addEventListener("change", function() {
            updateFamilyDropdown("addDivision", "addSubDivision", "addGroup", "addFamily");
          });
        }

        document.addEventListener("click", function(evt) {
          if (evt.target.closest && evt.target.closest(".multi-select")) return;
          document.querySelectorAll(".multi-select.open").forEach((select) => {
            select.classList.remove("open");
          });
        });

        const ncoInputs = [
          { a: document.getElementById('addNcoCodeFirst'), b: document.getElementById('addNcoCodeSecond') },
          { a: document.getElementById('addNco2004CodeFirst'), b: document.getElementById('addNco2004CodeSecond') },
          { a: document.getElementById('editNcoCodeFirst'), b: document.getElementById('editNcoCodeSecond') },
          { a: document.getElementById('editNco2004CodeFirst'), b: document.getElementById('editNco2004CodeSecond') },
        ];

        ncoInputs.forEach(({ a, b }) => {
          if (a) {
            a.addEventListener('input', () => {
              a.value = (a.value || '').replace(/\D/g, '').slice(0, 4);
              if (a.value.length === 4 && b) b.focus();
            });
          }
          if (b) {
            const max = b.id.toLowerCase().includes("2004") ? 2 : 4;
            b.addEventListener('input', () => {
              b.value = (b.value || '').replace(/\D/g, '').slice(0, max);
            });
          }
        });
      });

      function addOccupation() {
        const nco2015 = buildNcoCode("addNcoCodeFirst", "addNcoCodeSecond", 4);
        if (!nco2015.ok) {
          showNotification(nco2015.error, "error");
          return;
        }

        const data = {
          occupation_title: (document.getElementById("addTitle").value || "").trim(),
          nco_code: nco2015.code,
          nco_2004_code: "",
          description: (document.getElementById("addDescription").value || "").trim(),
          division: (document.getElementById("addDivision").value || "").trim(),
          sub_division: (document.getElementById("addSubDivision").value || "").trim(),
          group: (document.getElementById("addGroup").value || "").trim(),
          family: (document.getElementById("addFamily").value || "").trim(),
          admin_password: (document.getElementById("addAdminPassword").value || "").trim(),
        };
        const validationError = validateOccupationPayload(data, false);
        if (validationError) {
          showNotification(validationError, "error");
          return;
        }

        showLoading();
        fetch("/admin/api/occupations", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              const addModal = bootstrap.Modal.getInstance(document.getElementById("addModal"));
              if (addModal) {
                addModal.hide();
              }
              loadOccupations();
              showNotification("Occupation added successfully", "success");
            } else {
              showNotification(result.error || "Failed to add occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error adding occupation:", error);
            showNotification("Failed to add occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      async function loadAnalyticsData() {
        console.log("DEBUG: loadAnalyticsData called");

        if (window.analyticsLoading) {
          return;
        }
        window.analyticsLoading = true;

        try {
          const response = await fetch("/admin/api/prompt-history?limit=5000");
          if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
          }
          const historyData = await response.json();
          if (!Array.isArray(historyData)) {
            throw new Error("Invalid history data");
          }
          console.log("DEBUG: Fetched", historyData.length, "history entries");

          updateSearchAnalyticsCharts(historyData);
          updateNcoAnalysisMetrics();
          updateLastUpdateTime();

          if (document.getElementById("nco-analysis-tab")?.classList.contains("active")) {
            refreshNcoFilterOptions();
            drawNcoBubbleChart();
          }

          console.log("Analytics data loaded successfully");
        } catch (error) {
          console.error("Error loading analytics data:", error);
          showNotification("Failed to load analytics data", "error");
        } finally {
          window.analyticsLoading = false;
        }
      }

      // Refresh button click handler
      async function refreshAnalytics() {
        const btn = document.getElementById('refreshAnalyticsBtn') || document.querySelector('.refresh-btn');
        const originalContent = btn ? btn.innerHTML : '';
        if (btn) {
          btn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
          btn.disabled = true;
        }
        
        try {
          await loadAnalyticsData();
          showNotification('Analytics refreshed successfully', 'success');
        } catch (error) {
          showNotification('Failed to refresh analytics', 'error');
        } finally {
          if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
          }
        }
      }

      // Tab switching functionality
      function switchTab(tabName, element) {
        console.log('DEBUG: Switching to tab:', tabName);
        
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
          tab.classList.remove('active');
        });
        
        // Remove active class from all tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
          btn.classList.remove('active');
        });
        
        // Show selected tab
        const targetTab = document.getElementById(tabName);
        if (targetTab) {
          targetTab.classList.add('active');
        }
        
        if (element) {
          element.classList.add('active');
        }
        
        // Load data based on which tab is now active
        if (tabName === 'analytics-tab') {
          console.log('DEBUG: Analytics tab activated - loading analytics data');
          loadAnalyticsData();
          startAnalyticsAutoRefresh();
        } else if (tabName === 'database-tab') {
          console.log('DEBUG: Database tab activated - loading occupation data');
          loadOccupations();
          if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
          }
        } else if (tabName === 'nco-analysis-tab') {
          console.log('DEBUG: NCO Analysis tab activated');
          if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
          }
          loadNcoAnalysisData();
          startAnalyticsAutoRefresh();
        }
      }

      function deleteOccupation(rowId) {
        if (!confirm("Are you sure you want to delete this occupation? This action cannot be undone.")) {
          return;
        }

        const password = prompt("Please enter admin password to confirm deletion:");
        if (!password) return;

        showLoading();
        fetch(`/admin/api/occupations/${rowId}`, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ admin_password: password }),
        })
          .then((response) => response.json())
          .then((result) => {
            if (result.success) {
              loadOccupations();
              showNotification("Occupation deleted successfully", "success");
            } else {
              showNotification(result.error || "Failed to delete occupation", "error");
            }
          })
          .catch((error) => {
            console.error("Error deleting occupation:", error);
            showNotification("Failed to delete occupation", "error");
          })
          .finally(() => {
            hideLoading();
          });
      }

      // History functions
      function showPromptHistory(rowId) {
        const occupation = occupations.find((occ) => occ.row_id === rowId);
        if (!occupation) return;

        currentHistoryOccupationTitle = occupation.occupation_title;
        document.getElementById("historyOccupation").textContent = currentHistoryOccupationTitle;
        
        refreshPromptHistory();
        showModalById("historyModal");
      }

      function refreshPromptHistory() {
        if (!currentHistoryOccupationTitle) return;

        showLoading();
        fetch(`/admin/api/prompt-history?occupation_title=${encodeURIComponent(currentHistoryOccupationTitle)}&limit=100`)
          .then((response) => response.json())
          .then((data) => {
            currentHistoryRows = Array.isArray(data) ? data : [];
            displayPromptHistory();
          })
          .catch((error) => {
            console.error("Error loading prompt history:", error);
            currentHistoryRows = [];
            displayPromptHistory();
          })
          .finally(() => {
            hideLoading();
          });
      }

      function displayPromptHistory() {
        const tbody = document.getElementById("historyTableBody");
        const emptyDiv = document.getElementById("historyEmpty");

        if (currentHistoryRows.length === 0) {
          tbody.innerHTML = "";
          emptyDiv.style.display = "block";
          return;
        }

        emptyDiv.style.display = "none";
        tbody.innerHTML = currentHistoryRows.map((row) => `
          <tr>
            <td>${new Date(row.ts).toLocaleString()}</td>
            <td>${row.query}</td>
            <td>${row.top_k || "-"}</td>
            <td>${row.returned_count || "-"}</td>
            <td>${row.client_ip || "-"}</td>
          </tr>
        `).join("");
      }

      function filterPromptHistory() {
        const searchTerm = document.getElementById("historySearch").value.toLowerCase();
        const filtered = currentHistoryRows.filter((row) => 
          row.query.toLowerCase().includes(searchTerm)
        );
        
        const tbody = document.getElementById("historyTableBody");
        const emptyDiv = document.getElementById("historyEmpty");

        if (filtered.length === 0) {
          tbody.innerHTML = "";
          emptyDiv.style.display = "block";
          return;
        }

        emptyDiv.style.display = "none";
        tbody.innerHTML = filtered.map((row) => `
          <tr>
            <td>${new Date(row.ts).toLocaleString()}</td>
            <td>${row.query}</td>
            <td>${row.top_k || "-"}</td>
            <td>${row.returned_count || "-"}</td>
            <td>${row.client_ip || "-"}</td>
          </tr>
        `).join("");
      }

      // Utility functions
      function formatNcoCode(code) {
        if (!code) return "";
        const parts = code.split(".");
        if (parts.length === 2) {
          const left = parts[0].padStart(4, "0");
          const right = parts[1].padStart(4, "0");
          return `${left}.${right}`;
        }
        return code;
      }

      function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
          ${message}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
          notification.remove();
        }, 5000);
      }

      function updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleString(undefined, {
          year: 'numeric',
          month: 'short',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });

        const lastUpdateTimeElement = document.getElementById('lastUpdateTime');
        if (lastUpdateTimeElement) {
          lastUpdateTimeElement.textContent = `Last updated: ${timeString}`;
        }

        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
          lastUpdatedElement.textContent = timeString;
        }
        
        const reportTotalRecordsElement = document.getElementById('reportTotalRecords');
        if (reportTotalRecordsElement) {
          reportTotalRecordsElement.textContent = occupations.length.toLocaleString();
        }
      }

      // Chart refresh functions
      function refreshChart(chartName) {
        if (chartName === 'divisionChart') {
          updateChartsData();
        } else if (chartName === 'trendsChart') {
          loadAnalyticsData();
        }
        showNotification('Chart refreshed', 'success');
      }

      function refreshAnalyticsCharts() {
        updateChartsData();
        loadAnalyticsData();
      }

      function loadSearchAnalytics() {
        loadAnalyticsData();
      }

      function toggleAnalyticsSidebar() {
        const sidebar = document.getElementById('analyticsSidebar');
        if (sidebar.classList.contains('collapsed')) {
          sidebar.classList.remove('collapsed');
        } else {
          sidebar.classList.add('collapsed');
        }
      }

      // UI update functions for interactive filters
      function updateDateRangeUI(radio) {
        document.querySelectorAll('#dateRangeChips .chip').forEach(c => c.classList.remove('active'));
        radio.parentElement.classList.add('active');
        document.getElementById('analyticsDateRange').value = radio.value;
        
        const customDates = document.getElementById('customDatesContainer');
        if (radio.value === 'custom') {
          customDates.style.display = 'block';
        } else {
          customDates.style.display = 'none';
        }
        
        applyAnalyticsControls();
      }

      function updateGroupByUI(radio) {
        document.getElementById('analyticsGroupBy').value = radio.value;
        applyAnalyticsControls();
      }

      function updateOutcomeUI(radio) {
        document.querySelectorAll('#outcomeChips .chip').forEach(c => c.classList.remove('active'));
        radio.parentElement.classList.add('active');
        document.getElementById('analyticsOutcomeFilter').value = radio.value;
        applyAnalyticsControls();
      }

      function exportData(format) {
        if (!filteredOccupations || filteredOccupations.length === 0) {
          showNotification("No data to export", "error");
          return;
        }

        const data = filteredOccupations.map(occ => ({
          "Row ID": occ.row_id || "",
          "Occupation Title": occ.occupation_title || "",
          "NCO Code": occ.nco_code || "",
          "NCO 2004 Code": occ.nco_2004_code || "",
          "Division": occ.division || "",
          "Sub Division": occ.sub_division || "",
          "Group": occ.group || "",
          "Family": occ.family || "",
          "Description": occ.description || ""
        }));

        const date = new Date().toISOString().split('T')[0];

        if (format === 'excel') {
          if (typeof XLSX === 'undefined') {
            showNotification("Excel export library is not loaded.", "error");
            return;
          }
          const worksheet = XLSX.utils.json_to_sheet(data);
          const workbook = XLSX.utils.book_new();
          XLSX.utils.book_append_sheet(workbook, worksheet, "Occupations");
          XLSX.writeFile(workbook, `occupations_export_${date}.xlsx`);
          showNotification("Excel export downloaded successfully", "success");
        } else {
          // CSV Export
          const headers = Object.keys(data[0]);
          const csvRows = [headers.join(",")];
          
          function escapeCSV(str) {
            if (str == null) return '""';
            const stringified = String(str);
            if (stringified.search(/("|,|\n)/g) >= 0) {
              return `"${stringified.replace(/"/g, '""')}"`;
            }
            return stringified;
          }

          data.forEach(rowObj => {
            const row = headers.map(header => escapeCSV(rowObj[header]));
            csvRows.push(row.join(","));
          });
          
          const csvString = csvRows.join("\\n");
          const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
          
          const link = document.createElement("a");
          const url = URL.createObjectURL(blob);
          link.setAttribute("href", url);
          link.setAttribute("download", `occupations_export_${date}.csv`);
          link.style.visibility = 'hidden';
          
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          showNotification("CSV export downloaded successfully", "success");
        }
      }


      // --- NCO Search Demand Explorer ---
      let currentNcoLevel = "division";
      let ncoSelectedPath = [];
      let ncoSelectedNode = null;
      let ncoSimulation = null;
      let ncoSvg = null;
      let ncoNodesData = [];
      let mouseX = null;
      let mouseY = null;
      let ncoSimWidth = 800;
      let ncoSimHeight = 620;

      const ncoColorScale = d3.scaleOrdinal(d3.schemeCategory10);

      function searchEntryMatchesNcoFilters(entry, filters, skipField = "") {
        const fields = ["division", "sub_division", "group", "family"];
        return fields.every((field) => {
          if (field === skipField) return true;
          const selected = filters[field];
          if (!selected || selected.length === 0) return true;
          const value = getAnalyticsEntryProperty(entry, field);
          return selected.includes(value);
        });
      }

      function getFilteredNcoSearchHistory() {
        if (!allAnalyticsHistory || allAnalyticsHistory.length === 0) return [];

        const ncoFilters = typeof getNcoFilterValues === "function" ? getNcoFilterValues() : {
          division: [],
          sub_division: [],
          group: [],
          family: [],
        };

        let filtered = allAnalyticsHistory.filter((entry) => searchEntryMatchesNcoFilters(entry, ncoFilters));

        ncoSelectedPath.forEach((step) => {
          const field = step.level === "sub_division" ? "sub_division" : step.level;
          filtered = filtered.filter((entry) => getAnalyticsEntryProperty(entry, field) === step.name);
        });

        return filtered;
      }

      function populateNcoSearchFilter(selectId, allLabel, field, filters, changedId = "") {
        const root = document.getElementById(selectId);
        if (!root) return;
        const menu = root.querySelector(".multi-select-menu");
        if (!menu) return;

        const currentValues = getMultiSelectValues(selectId);
        menu.innerHTML = `
          <div class="multi-select-clear" onclick="resetMultiSelect('${selectId}')" style="padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #e5e7eb; color: #475569; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; background: #f8fafc; transition: background 0.2s ease;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
            <i class="fas fa-undo"></i> Reset Filter
          </div>
        `;

        const scopedFilters = { ...filters };
        scopedFilters[field] = [];

        let scopedHistory = allAnalyticsHistory || [];
        scopedHistory = scopedHistory.filter((entry) => searchEntryMatchesNcoFilters(entry, scopedFilters));
        ncoSelectedPath.forEach((step) => {
          const pathField = step.level === "sub_division" ? "sub_division" : step.level;
          scopedHistory = scopedHistory.filter((entry) => getAnalyticsEntryProperty(entry, pathField) === step.name);
        });

        const values = [...new Set(
          scopedHistory
            .map((entry) => getAnalyticsEntryProperty(entry, field))
            .filter(Boolean)
        )].sort();

        values.forEach((value, index) => {
          const optionId = `${selectId}-${index}`;
          const label = document.createElement("label");
          label.className = "multi-select-option";
          label.innerHTML = `
            <input type="checkbox" id="${optionId}" value="${escapeHtml(value)}" ${currentValues.includes(value) ? "checked" : ""} onchange="handleMultiSelectChange('${selectId}')" />
            <span>${escapeHtml(value)}</span>
          `;
          menu.appendChild(label);
        });

        if (selectId !== changedId) {
          const validSelections = currentValues.filter((value) => values.includes(value));
          setMultiSelectValues(selectId, validSelections);
        }
        updateMultiSelectDisplay(selectId, allLabel);
      }

      function updateNcoAnalysisMetrics() {
        const history = allAnalyticsHistory || [];
        const total = history.length;
        const successCount = history.filter(isSuccessfulAnalyticsEntry).length;
        const uniqueDivisions = new Set(
          history.map((entry) => getAnalyticsEntryProperty(entry, "division")).filter(Boolean)
        ).size;
        const uniqueOccupations = new Set(
          history.map((entry) => entry.occupation_title).filter(Boolean)
        ).size;

        setTextContent("ncoMetricTotalSearches", total.toLocaleString());
        setTextContent("ncoMetricDivisions", uniqueDivisions.toLocaleString());
        setTextContent("ncoMetricOccupations", uniqueOccupations.toLocaleString());
        setTextContent(
          "ncoMetricSuccess",
          total ? `${((successCount / total) * 100).toFixed(1)}%` : "0%"
        );
      }

      function lookupNcoHierarchyMeta(categoryName, level, sampleNcoCode = "") {
        const descFieldMap = {
          division: "division_description",
          sub_division: "sub_division_description",
          group: "group_description",
          family: "family_description",
        };
        const fieldMap = {
          division: "division",
          sub_division: "sub_division",
          group: "group",
          family: "family",
        };

        const field = fieldMap[level];
        const occ = (occupations || []).find((item) => item[field] === categoryName);
        const ncoCode = sampleNcoCode || occ?.nco_code || "";
        let code = "";

        if (ncoCode) {
          const base = String(ncoCode).split(".")[0];
          if (level === "division") code = base.substring(0, 1);
          else if (level === "sub_division") code = base.substring(0, 2);
          else if (level === "group") code = base.substring(0, 3);
          else code = base;
        }

        return {
          code,
          description: occ ? (occ[descFieldMap[level]] || "") : "",
        };
      }

      function getChildFieldForNcoLevel(level) {
        if (level === "division") return "sub_division";
        if (level === "sub_division") return "group";
        if (level === "group") return "family";
        return "";
      }

      function getAggregatedNcoData() {
        let filtered = getFilteredNcoSearchHistory().filter(
          (entry) => getAnalyticsEntryProperty(entry, currentNcoLevel)
        );
        if (filtered.length === 0) return [];

        const targetLevel = currentNcoLevel;
        const groups = {};

        filtered.forEach((entry) => {
          const key = getAnalyticsEntryProperty(entry, targetLevel);
          if (!key) return;

          const parentField = targetLevel === "sub_division"
            ? "division"
            : targetLevel === "group"
              ? "sub_division"
              : targetLevel === "family"
                ? "group"
                : "";
          const parentName = parentField ? getAnalyticsEntryProperty(entry, parentField) : "";
          const meta = lookupNcoHierarchyMeta(key, targetLevel, entry.nco_code || "");

          if (!groups[key]) {
            groups[key] = {
              name: key,
              code: meta.code,
              description: meta.description,
              searchEntries: [],
              parentName,
              subdivisions: new Set(),
              groups: new Set(),
              families: new Set(),
            };
          }

          groups[key].searchEntries.push(entry);
          const subDivision = getAnalyticsEntryProperty(entry, "sub_division");
          const groupName = getAnalyticsEntryProperty(entry, "group");
          const familyName = getAnalyticsEntryProperty(entry, "family");
          if (subDivision) groups[key].subdivisions.add(subDivision);
          if (groupName) groups[key].groups.add(groupName);
          if (familyName) groups[key].families.add(familyName);
        });

        return Object.values(groups).map((group) => {
          let childrenCount = 0;
          if (targetLevel === "division") childrenCount = group.subdivisions.size;
          else if (targetLevel === "sub_division") childrenCount = group.groups.size;
          else if (targetLevel === "group") childrenCount = group.families.size;
          else childrenCount = new Set(group.searchEntries.map((entry) => entry.occupation_title).filter(Boolean)).size;

          const searchCount = group.searchEntries.length;

          return {
            name: group.name,
            code: group.code,
            description: group.description,
            searchCount,
            occupationsCount: searchCount,
            childrenCount,
            searchEntries: group.searchEntries,
            parentName: group.parentName,
            level: targetLevel,
          };
        });
      }

      // Measure and wrap bubble label text
      let ncoMeasureCanvas = null;

      function measureBubbleTextWidth(text, fontSize, fontWeight = "700") {
        if (!ncoMeasureCanvas) {
          ncoMeasureCanvas = document.createElement("canvas");
        }
        const ctx = ncoMeasureCanvas.getContext("2d");
        ctx.font = `${fontWeight} ${fontSize}px Arial, sans-serif`;
        return ctx.measureText(text).width;
      }

      function wrapTextToLines(text, maxWidth, fontSize) {
        const words = String(text || "").split(/\s+/).filter(Boolean);
        if (!words.length) return [""];

        const lines = [];
        let current = "";

        words.forEach((word) => {
          const candidate = current ? `${current} ${word}` : word;
          if (measureBubbleTextWidth(candidate, fontSize) <= maxWidth) {
            current = candidate;
            return;
          }

          if (current) lines.push(current);

          if (measureBubbleTextWidth(word, fontSize) <= maxWidth) {
            current = word;
            return;
          }

          let chunk = "";
          for (const ch of word) {
            const next = chunk + ch;
            if (chunk && measureBubbleTextWidth(next, fontSize) > maxWidth) {
              lines.push(chunk);
              chunk = ch;
            } else {
              chunk = next;
            }
          }
          current = chunk;
        });

        if (current) lines.push(current);
        return lines;
      }

      function layoutNcoBubbleLabels(nodeSelection) {
        nodeSelection.each(function (d) {
          const group = d3.select(this);
          group.selectAll(".nco-bubble-label").remove();

          const r = d.r;
          const maxWidth = r * 1.7;
          const searchCount = d.searchCount ?? d.occupationsCount ?? 0;
          const searchLabel = `${searchCount.toLocaleString()} search${searchCount === 1 ? "" : "es"}`;
          const displayName = d.name.replace(/\//g, "/ ");

          let titleSize = Math.min(13, Math.max(7, r * 2.4 / Math.cbrt(displayName.length + 8)));
          let subSize = Math.max(8, Math.min(10, r / 5.5));
          const subGap = 5;
          const maxBlockHeight = Math.max(r * 1.35, 24);

          let lines = wrapTextToLines(displayName, maxWidth, titleSize);
          let lineHeight = titleSize * 1.18;

          while (lines.length * lineHeight + subGap + subSize > maxBlockHeight && titleSize > 7) {
            titleSize -= 0.5;
            lines = wrapTextToLines(displayName, maxWidth, titleSize);
            lineHeight = titleSize * 1.18;
          }

          if (lines.length * lineHeight + subGap + subSize > maxBlockHeight) {
            const maxLines = Math.max(
              1,
              Math.floor((maxBlockHeight - subGap - subSize) / lineHeight)
            );
            if (lines.length > maxLines) {
              lines = lines.slice(0, maxLines);
              let lastLine = lines[maxLines - 1];
              while (lastLine.length > 3 && measureBubbleTextWidth(`${lastLine}...`, titleSize) > maxWidth) {
                lastLine = lastLine.slice(0, -1);
              }
              lines[maxLines - 1] = `${lastLine}...`;
            }
          }

          const blockHeight = lines.length * lineHeight + subGap + subSize;
          const startY = -blockHeight / 2 + lineHeight / 2;

          const text = group
            .append("text")
            .attr("class", "nco-bubble-label")
            .attr("text-anchor", "middle")
            .style("pointer-events", "none");

          lines.forEach((line, index) => {
            text
              .append("tspan")
              .attr("class", "nco-bubble-text")
              .attr("x", 0)
              .attr("y", startY + index * lineHeight)
              .style("font-size", `${titleSize}px`)
              .style("font-weight", "700")
              .style("fill", "#0f172a")
              .style("font-family", "Arial, sans-serif")
              .text(line);
          });

          text
            .append("tspan")
            .attr("class", "nco-bubble-subtext")
            .attr("x", 0)
            .attr("y", startY + lines.length * lineHeight + subGap)
            .style("font-size", `${subSize}px`)
            .style("font-weight", "600")
            .style("fill", "#475569")
            .style("font-family", "Arial, sans-serif")
            .text(searchLabel);

          d._labelLines = lines.length;
        });
      }

      function drawNcoBubbleChart() {
        console.log("DEBUG: drawNcoBubbleChart called");
        
        ncoSvg = d3.select("#ncoBubbleSvg");
        if (ncoSvg.empty()) return;
        
        // Clear previous simulation and elements
        if (ncoSimulation) {
          ncoSimulation.stop();
        }
        ncoSvg.selectAll("*").remove();

        const containerNode = ncoSvg.node().parentNode;
        const width = containerNode.clientWidth || 800;
        const height = 620;
        ncoSvg.attr("width", width).attr("height", height);

        const data = getAggregatedNcoData();
        ncoNodesData = data;
        
        if (data.length === 0) {
          ncoSvg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2)
            .attr("text-anchor", "middle")
            .attr("fill", "#94a3b8")
            .attr("font-size", "16px")
            .text("No user searches found matching the current filters.");
          return;
        }

        // Define scales for radius
        const minCount = d3.min(data, d => d.occupationsCount) || 1;
        const maxCount = d3.max(data, d => d.occupationsCount) || 1;
        
        const rScale = d3.scaleSqrt()
          .domain([minCount, maxCount])
          .range([data.length > 50 ? 20 : 35, data.length > 50 ? 75 : 95]);

        let maxScaleFactor = 1;
        data.forEach((d) => {
          d.r = rScale(d.occupationsCount);
          const displayName = d.name.replace(/\//g, "/ ");
          let requiredR = d.r;

          for (let testR = Math.max(d.r, 28); testR <= d.r * 3.5; testR += 4) {
            const titleSize = Math.min(13, Math.max(7, testR * 2.4 / Math.cbrt(displayName.length + 8)));
            const subSize = Math.max(8, Math.min(10, testR / 5.5));
            const lines = wrapTextToLines(displayName, testR * 1.7, titleSize);
            const blockHeight = lines.length * titleSize * 1.18 + subSize + 5;
            if (blockHeight <= testR * 1.9) {
              requiredR = testR;
              break;
            }
            requiredR = testR;
          }

          if (requiredR > d.r) {
            maxScaleFactor = Math.max(maxScaleFactor, requiredR / d.r);
          }
        });
        
        maxScaleFactor = Math.min(maxScaleFactor, 3.5);

        let totalArea = 0;
        data.forEach(d => {
          d.r *= maxScaleFactor;
          totalArea += Math.PI * d.r * d.r;
        });

        ncoSimWidth = width;
        ncoSimHeight = height;
        const requiredArea = totalArea * 2.8; // Enough room to breathe
        const currentArea = width * height;
        if (requiredArea > currentArea) {
            const scale = Math.sqrt(requiredArea / currentArea);
            ncoSimWidth = width * scale;
            ncoSimHeight = height * scale;
        }

        data.forEach((d, i) => {
          d.x = ncoSimWidth / 2 + (Math.random() - 0.5) * ncoSimWidth * 0.5;
          d.y = ncoSimHeight / 2 + (Math.random() - 0.5) * ncoSimHeight * 0.5;
        });

        // Legend setup
        const legendContainer = document.getElementById("ncoLegend");
        legendContainer.innerHTML = "";
        
        const uniqueParents = [...new Set(data.map(d => d.level === 'division' ? d.name : d.parentName))].filter(Boolean);
        uniqueParents.forEach(parentName => {
          const color = ncoColorScale(parentName);
          const div = document.createElement("div");
          div.className = "legend-item";
          div.innerHTML = `
            <div class="legend-color" style="background: ${color}"></div>
            <span>${parentName}</span>
          `;
          legendContainer.appendChild(div);
        });

        // Setup filters for neon glowing style
        const defs = ncoSvg.append("defs");
        
        const dropShadow = defs.append("filter")
          .attr("id", "bubbleShadow")
          .attr("x", "-20%").attr("y", "-20%")
          .attr("width", "140%").attr("height", "140%");
        dropShadow.append("feDropShadow")
          .attr("dx", "0").attr("dy", "0")
          .attr("stdDeviation", "8")
          .attr("flood-color", "#0f172a")
          .attr("flood-opacity", "0.25");

        const gMain = ncoSvg.append("g");
        const tooltip = d3.select("#ncoBubbleTooltip");

        // Physics parameters
        const repulsionVal = +document.getElementById("paramRepulsion").value;
        const attractionVal = +document.getElementById("paramAttraction").value / 100;

        ncoSimulation = d3.forceSimulation(data)
          .force("charge", d3.forceManyBody().strength(d => -Math.pow(d.r, 1.2) * repulsionVal * 0.1))
          .force("x", d3.forceX(ncoSimWidth / 2).strength(attractionVal))
          .force("y", d3.forceY(ncoSimHeight / 2).strength(attractionVal))
          .force("collide", d3.forceCollide(d => d.r + 4).iterations(3));

        // Create groups
        const node = gMain.selectAll(".node")
          .data(data)
          .enter()
          .append("g")
          .attr("class", "node")
          .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended)
          );

        // Bubble circle - Neon Hologram Style
        node.append("circle")
          .attr("class", "nco-bubble")
          .attr("r", d => d.r)
          .attr("fill", d => {
             const parentName = d.level === 'division' ? d.name : d.parentName;
             let c = d3.color(ncoColorScale(parentName));
             c.opacity = 0.15;
             return c.toString();
          })
          .style("filter", "url(#bubbleShadow)")
          .style("stroke", d => {
             const parentName = d.level === 'division' ? d.name : d.parentName;
             return ncoColorScale(parentName);
          })
          .style("stroke-width", "2.5px")
          .on("mouseover", function(event, d) {
             const parentName = d.level === 'division' ? d.name : d.parentName;
             let c = d3.color(ncoColorScale(parentName));
             c.opacity = 0.4;
             d3.select(this).style("fill", c.toString())
                            .style("filter", `drop-shadow(0 0 15px ${ncoColorScale(parentName)})`);
             
             tooltip.style("opacity", 1)
               .html(`
                 <h5>${d.name}</h5>
                 <div class="meta-row"><span>Code:</span><span class="meta-val">${d.code}</span></div>
                 <div class="meta-row"><span>Level:</span><span class="meta-val" style="text-transform: capitalize;">${d.level.replace('_', ' ')}</span></div>
                 <div class="meta-row"><span>${d.level === 'family' ? 'Matched Jobs' : 'Sub-categories'}:</span><span class="meta-val">${d.childrenCount}</span></div>
                 <div class="meta-row"><span>Total Searches:</span><span class="meta-val">${d.searchCount ?? d.occupationsCount}</span></div>
                 <p style="margin: 8px 0 0 0; font-size:11px; color:#94a3b8; line-height: 1.4; border-top: 1px solid #334155; padding-top:6px;">
                   ${d.description ? d.description.substring(0, 120) + '...' : 'No description available.'}
                 </p>
               `);
          })
          .on("mousemove", function(event) {
            const containerRect = containerNode.getBoundingClientRect();
            tooltip
              .style("left", (event.clientX - containerRect.left + 15) + "px")
              .style("top", (event.clientY - containerRect.top + 15) + "px");
          })
          .on("mouseout", function(event, d) {
             const parentName = d.level === 'division' ? d.name : d.parentName;
             let c = d3.color(ncoColorScale(parentName));
             c.opacity = 0.15;
             d3.select(this).style("fill", c.toString())
                            .style("filter", "url(#bubbleShadow)");
             tooltip.style("opacity", 0);
          })
          .on("click", function(event, d) {
            selectNcoNode(d, this);
            event.stopPropagation();
          });


        // Bubble labels (title + search count in one centered block)
        layoutNcoBubbleLabels(node);



        // Zoom / Pan setup
        let initialScale = 1;
        if (ncoSimWidth > width || ncoSimHeight > height) {
           initialScale = Math.min(width / ncoSimWidth, height / ncoSimHeight) * 0.9;
        }
        
        const zoom = d3.zoom()
          .scaleExtent([0.1, 8])
          .on("zoom", (event) => {
            gMain.attr("transform", event.transform);
          });
        ncoSvg.call(zoom);

        // Apply initial transform to center the simulation in the viewport
        let tx = (width - ncoSimWidth * initialScale) / 2;
        let ty = (height - ncoSimHeight * initialScale) / 2;
        ncoSvg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(initialScale));

        // Mouse attraction physics helpers
        ncoSvg.on("mousemove", function(event) {
          const coords = d3.pointer(event);
          mouseX = coords[0];
          mouseY = coords[1];
        });

        ncoSvg.on("mouseleave", function() {
          mouseX = null;
          mouseY = null;
        });

        // Clicking SVG canvas deselects active node
        ncoSvg.on("click", function() {
          deselectNcoNode();
        });

        ncoSimulation.on("tick", () => {
          if (mouseX !== null && mouseY !== null) {
            data.forEach(d => {
              const dx = mouseX - d.x;
              const dy = mouseY - d.y;
              const dist = Math.sqrt(dx * dx + dy * dy);
              if (dist < 220 && dist > 10) {
                d.vx += (dx / dist) * 0.08;
                d.vy += (dy / dist) * 0.08;
              }
            });
          }

          node.attr("transform", d => {
            d.x = Math.max(d.r, Math.min(ncoSimWidth - d.r, d.x));
            d.y = Math.max(d.r, Math.min(ncoSimHeight - d.r, d.y));
            return `translate(${d.x}, ${d.y})`;
          });
        });

        function dragstarted(event, d) {
          if (!event.active) ncoSimulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        }

        function dragged(event, d) {
          d.fx = event.x;
          d.fy = event.y;
        }

        function dragended(event, d) {
          if (!event.active) ncoSimulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }
        
        highlightNcoBubbles();
      }

      function selectNcoNode(d, element) {
        ncoSelectedNode = d;

        d3.selectAll(".nco-bubble")
          .style("stroke-width", 2.5)
          .style("filter", "url(#bubbleShadow)");

        if (element) {
          d3.select(element)
            .style("stroke-width", 5)
            .style("filter", "drop-shadow(0 0 15px rgba(255, 255, 255, 0.8))");
        }

        document.getElementById("ncoDetailFloating").classList.add("active");
        document.getElementById("ncoDetailPlaceholder").style.display = "none";
        document.getElementById("ncoDetailContent").style.display = "flex";

        const titleEl = document.getElementById("ncoDetailName");
        const typeEl = document.getElementById("ncoDetailType");
        const codeEl = document.getElementById("ncoDetailCode");
        const descEl = document.getElementById("ncoDetailDesc");
        const statChildrenEl = document.getElementById("ncoDetailStatChildren");
        const statChildrenLabel = document.getElementById("ncoDetailStatChildrenLabel");
        const statJobsEl = document.getElementById("ncoDetailStatJobs");
        const childListEl = document.getElementById("ncoChildList");
        const btnDrillDown = document.getElementById("btnNcoDrillDown");

        titleEl.textContent = d.name;
        codeEl.textContent = `CODE: ${d.code}`;
        descEl.textContent = d.description || "No specific classification description registered for this entry.";
        
        let levelText = d.level;
        if (levelText === "sub_division") levelText = "Sub-Division";
        typeEl.textContent = levelText;
        typeEl.className = `badge mb-2 bg-${d.level === 'division' ? 'primary' : d.level === 'sub_division' ? 'success' : d.level === 'group' ? 'warning' : 'danger'}`;

        statJobsEl.textContent = (d.searchCount ?? d.occupationsCount).toLocaleString();
        
        let childrenLabel = "Children";
        if (d.level === "division") {
          childrenLabel = "Sub Divs Searched";
        } else if (d.level === "sub_division") {
          childrenLabel = "Groups Searched";
        } else if (d.level === "group") {
          childrenLabel = "Families Searched";
        } else if (d.level === "family") {
          childrenLabel = "Matched Jobs";
        }
        statChildrenLabel.textContent = childrenLabel;
        statChildrenEl.textContent = d.childrenCount;

        childListEl.innerHTML = "";
        
        if (d.level === "family") {
          btnDrillDown.disabled = true;
          btnDrillDown.innerHTML = `<i class="fas fa-search-plus"></i> Drill Down (Max Depth)`;
          
          const occupationCounts = {};
          d.searchEntries.forEach((entry) => {
            const title = entry.occupation_title || "Unknown occupation";
            occupationCounts[title] = (occupationCounts[title] || 0) + 1;
          });

          Object.entries(occupationCounts)
            .sort(([, a], [, b]) => b - a)
            .forEach(([title, count]) => {
            const item = document.createElement("div");
            item.className = "child-list-item";
            item.innerHTML = `
              <div style="font-weight: 500;">${escapeHtml(title)}</div>
              <div style="font-size:11px; color:#6b7280;">${count} search${count === 1 ? "" : "es"}</div>
            `;
            item.onclick = (e) => {
              switchTab('database-tab', document.querySelector('[onclick*="database-tab"]'));
              const searchInput = document.getElementById("searchInput");
              if (searchInput) {
                searchInput.value = title;
                searchOccupations();
              }
              e.stopPropagation();
            };
            childListEl.appendChild(item);
          });
        } else {
          btnDrillDown.disabled = false;
          btnDrillDown.innerHTML = `<i class="fas fa-search-plus"></i> Drill Down`;

          const childField = getChildFieldForNcoLevel(d.level);
          const childCounts = {};
          d.searchEntries.forEach((entry) => {
            const childName = getAnalyticsEntryProperty(entry, childField);
            if (!childName) return;
            childCounts[childName] = (childCounts[childName] || 0) + 1;
          });

          Object.entries(childCounts)
            .sort(([, a], [, b]) => b - a)
            .forEach(([childName, count]) => {
            const item = document.createElement("div");
            item.className = "child-list-item";
            item.innerHTML = `
              <div>${escapeHtml(childName)}</div>
              <div style="font-size:11px; color:#6b7280;">${count} search${count === 1 ? "" : "es"}</div>
            `;
            item.onclick = (e) => {
              drillDownToNode(d, childName);
              e.stopPropagation();
            };
            childListEl.appendChild(item);
          });
        }
      }

      function deselectNcoNode() {
        ncoSelectedNode = null;
        d3.selectAll(".nco-bubble")
          .style("stroke-width", 2.5)
          .style("filter", "url(#bubbleShadow)");

        document.getElementById("ncoDetailFloating").classList.remove("active");
        document.getElementById("ncoDetailPlaceholder").style.display = "block";
        document.getElementById("ncoDetailContent").style.display = "none";
      }

      function drillDownSelected() {
        if (!ncoSelectedNode) return;
        drillDownToNode(null, ncoSelectedNode.name);
      }

      function drillDownToNode(parentNode, categoryName) {
        const levelOrder = ["division", "sub_division", "group", "family"];
        let targetLevelIdx = levelOrder.indexOf(currentNcoLevel) + 1;
        
        if (targetLevelIdx >= levelOrder.length) return;
        
        ncoSelectedPath.push({
          level: currentNcoLevel,
          name: parentNode ? parentNode.name : categoryName
        });
        
        currentNcoLevel = levelOrder[targetLevelIdx];
        
        const levelRadio = document.getElementById(`level${currentNcoLevel === 'sub_division' ? 'Sub' : currentNcoLevel === 'group' ? 'Group' : currentNcoLevel === 'family' ? 'Family' : 'Div'}`);
        if (levelRadio) levelRadio.checked = true;

        updateNcoBreadcrumbs();
        deselectNcoNode();
        drawNcoBubbleChart();
      }

      function drillUpOneLevel() {
        if (ncoSelectedPath.length === 0) return;
        
        const previousStep = ncoSelectedPath.pop();
        currentNcoLevel = previousStep.level;

        const levelRadio = document.getElementById(`level${currentNcoLevel === 'sub_division' ? 'Sub' : currentNcoLevel === 'group' ? 'Group' : currentNcoLevel === 'family' ? 'Family' : 'Div'}`);
        if (levelRadio) levelRadio.checked = true;

        updateNcoBreadcrumbs();
        deselectNcoNode();
        drawNcoBubbleChart();
      }

      function drillUpTo(pathIndex) {
        if (pathIndex === 0) {
          ncoSelectedPath = [];
          currentNcoLevel = "division";
        } else {
          ncoSelectedPath = ncoSelectedPath.slice(0, pathIndex);
          currentNcoLevel = ncoSelectedPath[ncoSelectedPath.length - 1].level;
        }

        const levelRadio = document.getElementById(`level${currentNcoLevel === 'sub_division' ? 'Sub' : currentNcoLevel === 'group' ? 'Group' : currentNcoLevel === 'family' ? 'Family' : 'Div'}`);
        if (levelRadio) levelRadio.checked = true;

        updateNcoBreadcrumbs();
        deselectNcoNode();
        drawNcoBubbleChart();
      }

      function changeNcoLevel(newLevel) {
        currentNcoLevel = newLevel;
        const levelOrder = ["division", "sub_division", "group", "family"];
        const targetIdx = levelOrder.indexOf(newLevel);
        
        ncoSelectedPath = ncoSelectedPath.filter(step => {
          const stepIdx = levelOrder.indexOf(step.level);
          return stepIdx < targetIdx;
        });

        updateNcoBreadcrumbs();
        deselectNcoNode();
        drawNcoBubbleChart();
      }

      function updateNcoBreadcrumbs() {
        const breadcrumbs = document.getElementById("ncoBreadcrumbs");
        if (!breadcrumbs) return;

        let html = `<li class="breadcrumb-item"><a href="javascript:void(0)" onclick="drillUpTo(0)">All Divisions</a></li>`;
        
        ncoSelectedPath.forEach((step, idx) => {
          if (idx === ncoSelectedPath.length - 1) {
            html += `<li class="breadcrumb-item active" aria-current="page">${step.name}</li>`;
          } else {
            html += `<li class="breadcrumb-item"><a href="javascript:void(0)" onclick="drillUpTo(${idx + 1})">${step.name}</a></li>`;
          }
        });

        breadcrumbs.innerHTML = html;

        const btnBack = document.getElementById("btnNcoBack");
        if (btnBack) {
          btnBack.disabled = ncoSelectedPath.length === 0;
        }
      }

      function highlightNcoBubbles() {
        const q = (document.getElementById("ncoBubbleSearch").value || "").toLowerCase().trim();
        const bubbles = d3.selectAll(".nco-bubble");
        
        if (!q) {
          bubbles.classed("searched", false).style("opacity", 1);
          d3.selectAll(".nco-bubble-label").style("opacity", 1);
          return;
        }

        bubbles.each(function(d) {
          const match = d.name.toLowerCase().includes(q) || d.code.toLowerCase().includes(q);
          d3.select(this)
            .classed("searched", match)
            .style("opacity", match ? 1 : 0.25);
        });

        d3.selectAll(".nco-bubble-label").style("opacity", function() {
          const datum = d3.select(this.parentNode).datum();
          if (!datum) return 1;
          const match = datum.name.toLowerCase().includes(q) || datum.code.toLowerCase().includes(q);
          return match ? 1 : 0.15;
        });
      }

      function updatePhysicsParams() {
        const repulsionVal = +document.getElementById("paramRepulsion").value;
        const attractionVal = +document.getElementById("paramAttraction").value / 100;

        document.getElementById("valRepulsion").textContent = repulsionVal;
        document.getElementById("valAttraction").textContent = (attractionVal * 100).toFixed(0) + "%";

        if (ncoSimulation) {
          ncoSimulation.force("charge", d3.forceManyBody().strength(d => -Math.pow(d.r, 1.2) * repulsionVal * 0.1));
          const containerNode = d3.select("#ncoBubbleSvg").node().parentNode;
          ncoSimulation.force("x", d3.forceX(ncoSimWidth / 2).strength(attractionVal));
          ncoSimulation.force("y", d3.forceY(ncoSimHeight / 2).strength(attractionVal));
          ncoSimulation.alpha(0.3).restart();
        }
      }

      function resetNcoExplorer() {
        ncoSelectedPath = [];
        currentNcoLevel = "division";
        document.getElementById("ncoBubbleSearch").value = "";
        
        const levelRadio = document.getElementById("levelDiv");
        if (levelRadio) levelRadio.checked = true;
        
        document.getElementById("paramRepulsion").value = 20;
        document.getElementById("paramAttraction").value = 5;
        document.getElementById("valRepulsion").textContent = "20";
        document.getElementById("valAttraction").textContent = "5%";

        updateNcoBreadcrumbs();
        deselectNcoNode();
        drawNcoBubbleChart();
      }

      function lookupInDatabase() {
        if (!ncoSelectedNode) return;
        switchTab('database-tab', document.querySelector('[onclick*="database-tab"]'));
        
        resetAllDatabaseFilters();
        
        const searchInput = document.getElementById("searchInput");
        if (searchInput) {
          searchInput.value = ncoSelectedNode.name;
          searchOccupations();
        }
      }
