var packet_list = {};

var tx_data = [];
var rx_data = [];

var packet_types_data = {};

var mem_current = []
var mem_peak = []

var thread_current = []

// Chart instances for theme updates
var packets_chart = null;
var packet_types_chart = null;
var message_chart = null;
var ack_chart = null;
var memory_chart = null;
var thread_chart = null;

// Get theme-aware colors
function getChartTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        textColor: isDark ? '#cbd5e1' : '#1e293b',
        textColorSecondary: isDark ? '#94a3b8' : '#64748b',
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        gridColor: isDark ? '#334155' : '#e2e8f0',
        borderColor: isDark ? '#475569' : '#cbd5e1',
        tooltipBg: isDark ? '#0f172a' : '#ffffff',
        tooltipBorder: isDark ? '#334155' : '#e2e8f0',
        tooltipText: isDark ? '#f1f5f9' : '#1e293b',
    };
}

// Get common chart options with theme support
function getChartBaseOptions(titleText) {
    const theme = getChartTheme();
    return {
        backgroundColor: theme.backgroundColor,
        textStyle: {
            color: theme.textColor,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
        },
        title: {
            text: titleText,
            textStyle: {
                color: theme.textColor,
                fontSize: 16,
                fontWeight: 600,
            },
            left: 'center',
        },
        legend: {
            textStyle: {
                color: theme.textColor,
            },
            top: '10%',
        },
        tooltip: {
            backgroundColor: theme.tooltipBg,
            borderColor: theme.tooltipBorder,
            borderWidth: 1,
            textStyle: {
                color: theme.tooltipText,
            },
            axisPointer: {
                lineStyle: {
                    color: theme.textColorSecondary,
                },
            },
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true,
        },
        xAxis: {
            type: 'time',
            axisLine: {
                lineStyle: {
                    color: theme.gridColor,
                },
            },
            axisLabel: {
                color: theme.textColorSecondary,
            },
            splitLine: {
                lineStyle: {
                    color: theme.gridColor,
                    type: 'dashed',
                },
            },
        },
        yAxis: {
            type: 'value',
            axisLine: {
                lineStyle: {
                    color: theme.gridColor,
                },
            },
            axisLabel: {
                color: theme.textColorSecondary,
            },
            splitLine: {
                lineStyle: {
                    color: theme.gridColor,
                    type: 'dashed',
                },
            },
        },
    };
}

// Update chart theme
function updateChartTheme(chart) {
    if (!chart) return;
    const theme = getChartTheme();
    chart.setOption({
        backgroundColor: theme.backgroundColor,
        textStyle: {
            color: theme.textColor,
        },
        title: {
            textStyle: {
                color: theme.textColor,
            },
        },
        legend: {
            textStyle: {
                color: theme.textColor,
            },
        },
        tooltip: {
            backgroundColor: theme.tooltipBg,
            borderColor: theme.tooltipBorder,
            textStyle: {
                color: theme.tooltipText,
            },
            axisPointer: {
                lineStyle: {
                    color: theme.textColorSecondary,
                },
            },
        },
        xAxis: {
            axisLine: {
                lineStyle: {
                    color: theme.gridColor,
                },
            },
            axisLabel: {
                color: theme.textColorSecondary,
            },
            splitLine: {
                lineStyle: {
                    color: theme.gridColor,
                    type: 'dashed',
                },
            },
        },
        yAxis: {
            axisLine: {
                lineStyle: {
                    color: theme.gridColor,
                },
            },
            axisLabel: {
                color: theme.textColorSecondary,
            },
            splitLine: {
                lineStyle: {
                    color: theme.gridColor,
                    type: 'dashed',
                },
            },
        },
        toolbox: {
            iconStyle: {
                borderColor: theme.textColorSecondary,
            },
        },
    }, { notMerge: false });
}

// Update all charts theme
function updateAllChartsTheme() {
    updateChartTheme(packets_chart);
    updateChartTheme(packet_types_chart);
    updateChartTheme(message_chart);
    updateChartTheme(ack_chart);
    updateChartTheme(memory_chart);
    updateChartTheme(thread_chart);
}


function start_charts() {
    console.log("start_charts() called");
    // Initialize the echarts instance based on the prepared dom
    create_packets_chart();
    create_packets_types_chart();
    create_messages_chart();
    create_ack_chart();
    create_memory_chart();
    create_thread_chart();
}


function create_packets_chart() {
    // The packets totals TX/RX chart.
    pkt_c_canvas = document.getElementById('packetsChart');
    packets_chart = echarts.init(pkt_c_canvas);

    // Get theme-aware base options
    var baseOptions = getChartBaseOptions('APRS Packet totals');

    // Specify the configuration items and data for the chart
    var option = Object.assign({}, baseOptions, {
      toolbox: {
        show : true,
        iconStyle: {
            borderColor: getChartTheme().textColorSecondary,
        },
        feature : {
           mark : {show: true},
           dataView : {show: true, readOnly: true},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable : true,
      series: [
          {
             name: 'tx',
             type: 'line',
             smooth: true,
             color: '#ef4444',
             encode: {
               x: 'timestamp',
               y: 'tx'
             }
          },{
             name: 'rx',
             type: 'line',
             smooth: true,
             color: '#10b981',
             encode: {
               x: 'timestamp',
               y: 'rx'
          }
      }]
    });

    // Display the chart using the configuration items and data just specified.
    packets_chart.setOption(option);
}


function create_packets_types_chart() {
    // The packets types chart
    pkt_types_canvas = document.getElementById('packetTypesChart');
    packet_types_chart = echarts.init(pkt_types_canvas);

    // Get theme-aware base options
    var baseOptions = getChartBaseOptions('Packet Types');

    // The series and data are built and updated on the fly
    // as packets come in.
    var option = Object.assign({}, baseOptions, {
      toolbox: {
        show : true,
        iconStyle: {
            borderColor: getChartTheme().textColorSecondary,
        },
        feature : {
           mark : {show: true},
           dataView : {show: true, readOnly: true},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable : true,
    });

    packet_types_chart.setOption(option);
}


function create_messages_chart() {
    msg_c_canvas = document.getElementById('messagesChart');
    message_chart = echarts.init(msg_c_canvas);

    // Get theme-aware base options
    var baseOptions = getChartBaseOptions('Message Packets');

    // Specify the configuration items and data for the chart
    var option = Object.assign({}, baseOptions, {
      toolbox: {
        show: true,
        iconStyle: {
            borderColor: getChartTheme().textColorSecondary,
        },
        feature: {
           mark : {show: true},
           dataView : {show: true, readOnly: true},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable: true,
      series: [
          {
             name: 'tx',
             type: 'line',
             smooth: true,
             color: '#ef4444',
             encode: {
               x: 'timestamp',
               y: 'tx'
             }
          },{
             name: 'rx',
             type: 'line',
             smooth: true,
             color: '#10b981',
             encode: {
               x: 'timestamp',
               y: 'rx'
          }
      }]
    });

    // Display the chart using the configuration items and data just specified.
    message_chart.setOption(option);
}

function create_ack_chart() {
    ack_canvas = document.getElementById('acksChart');
    ack_chart = echarts.init(ack_canvas);

    // Get theme-aware base options
    var baseOptions = getChartBaseOptions('Ack Packets');

    // Specify the configuration items and data for the chart
    var option = Object.assign({}, baseOptions, {
      toolbox: {
        show: true,
        iconStyle: {
            borderColor: getChartTheme().textColorSecondary,
        },
        feature: {
           mark : {show: true},
           dataView : {show: true, readOnly: false},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable: true,
      series: [
          {
             name: 'tx',
             type: 'line',
             smooth: true,
             color: '#ef4444',
             encode: {
               x: 'timestamp',
               y: 'tx'
             }
          },{
             name: 'rx',
             type: 'line',
             smooth: true,
             color: '#10b981',
             encode: {
               x: 'timestamp',
               y: 'rx'
          }
      }]
    });

    ack_chart.setOption(option);
}

function create_memory_chart() {
    ack_canvas = document.getElementById('memChart');
    memory_chart = echarts.init(ack_canvas);

    // Specify the configuration items and data for the chart
    var option = {
      title: {
          text: 'Memory Usage'
      },
      legend: {},
      tooltip: {
        trigger: 'axis'
      },
      toolbox: {
        show: true,
        feature: {
           mark : {show: true},
           dataView : {show: true, readOnly: false},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable: true,
      xAxis: { type: 'time' },
      yAxis: { },
      series: [
          {
             name: 'current',
             type: 'line',
             smooth: true,
             color: 'red',
             encode: {
               x: 'timestamp',
               y: 'current' // refer sensor 1 value
             }
          },{
             name: 'peak',
             type: 'line',
             smooth: true,
             encode: {
               x: 'timestamp',
               y: 'peak'
          }
      }]
    };

    memory_chart.setOption(option);
}

function create_thread_chart() {
    thread_canvas = document.getElementById('threadChart');
    thread_chart = echarts.init(thread_canvas);

    // Get theme-aware base options
    var baseOptions = getChartBaseOptions('Active Threads');

    // Specify the configuration items and data for the chart
    var option = Object.assign({}, baseOptions, {
      toolbox: {
        show: true,
        iconStyle: {
            borderColor: getChartTheme().textColorSecondary,
        },
        feature: {
           mark : {show: true},
           dataView : {show: true, readOnly: false},
           magicType : {show: true, type: ['line', 'bar']},
           restore : {show: true},
           saveAsImage : {show: true}
        }
      },
      calculable: true,
      series: [
          {
             name: 'current',
             type: 'line',
             smooth: true,
             color: '#2563eb',
             encode: {
               x: 'timestamp',
               y: 'current'
             }
          }
      ]
    });

    thread_chart.setOption(option);
}




function updatePacketData(chart, time, first, second) {
    tx_data.push([time, first]);
    rx_data.push([time, second]);
    const theme = getChartTheme();
    option = {
        backgroundColor: theme.backgroundColor,
        series: [
          {
            name: 'tx',
            data: tx_data,
            color: '#ef4444',
          },
          {
            name: 'rx',
            data: rx_data,
            color: '#10b981',
          }
        ]
    }
    chart.setOption(option);
}

function updatePacketTypesData(time, typesdata) {
    //The options series is created on the fly each time based on
    //the packet types we have in the data
    var series = []

    for (const k in typesdata) {
        tx = [time, typesdata[k]["tx"]]
        rx = [time, typesdata[k]["rx"]]

        if (packet_types_data.hasOwnProperty(k)) {
            packet_types_data[k]["tx"].push(tx)
            packet_types_data[k]["rx"].push(rx)
        } else {
            packet_types_data[k] = {'tx': [tx], 'rx': [rx]}
        }
    }
}

function updatePacketTypesChart() {
  series = []
  for (const k in packet_types_data) {
      entry = {
          name: k+"tx",
          data: packet_types_data[k]["tx"],
          type: 'line',
          smooth: true,
          color: '#ef4444',
          encode: {
            x: 'timestamp',
            y: k+'tx'
          }
      }
      series.push(entry)
      entry = {
          name: k+"rx",
          data: packet_types_data[k]["rx"],
          type: 'line',
          smooth: true,
          color: '#10b981',
          encode: {
            x: 'timestamp',
            y: k+'rx'
          }
      }
      series.push(entry)
  }

  const theme = getChartTheme();
  option = {
      backgroundColor: theme.backgroundColor,
      series: series
  }
  packet_types_chart.setOption(option);
}

function updateTypeChart(chart, key)  {
    //Generic function to update a packet type chart
    if (! packet_types_data.hasOwnProperty(key)) {
        return;
    }

    if (! packet_types_data[key].hasOwnProperty('tx')) {
        return;
    }
    const theme = getChartTheme();
    var option = {
        backgroundColor: theme.backgroundColor,
        series: [{
            name: "tx",
            data: packet_types_data[key]["tx"],
            color: '#ef4444',
        },
        {
            name: "rx",
            data: packet_types_data[key]["rx"],
            color: '#10b981',
        }]
    }

   chart.setOption(option);
}

function updateMemChart(time, current, peak) {
    mem_current.push([time, current]);
    mem_peak.push([time, peak]);
    const theme = getChartTheme();
    option = {
        backgroundColor: theme.backgroundColor,
        series: [
          {
            name: 'current',
            data: mem_current,
            color: '#3b82f6',
          },
          {
            name: 'peak',
            data: mem_peak,
            color: '#ef4444',
          }
        ]
    }
    memory_chart.setOption(option);
}

function updateThreadChart(time, threads) {
    keys = Object.keys(threads);
    thread_count = keys.length;
    thread_current.push([time, thread_count]);
    const theme = getChartTheme();
    option = {
        backgroundColor: theme.backgroundColor,
        series: [
              {
                name: 'current',
                data: thread_current,
                color: '#2563eb',
              }
            ]
    }
    thread_chart.setOption(option);
}

function updateMessagesChart() {
    updateTypeChart(message_chart, "MessagePacket")
}

function updateAcksChart() {
    updateTypeChart(ack_chart, "AckPacket")
}

function update_stats( data ) {
    console.log("update_stats() echarts.js called")
    stats = data["stats"];
    our_callsign = stats["APRSDStats"]["callsign"];
    $("#version").text( stats["APRSDStats"]["version"] );
    $("#aprs_connection").html( stats["aprs_connection"] );
    $("#uptime").text( "uptime: " + stats["APRSDStats"]["uptime"] );
    const html_pretty = Prism.highlight(JSON.stringify(data, null, '\t'), Prism.languages.json, 'json');
    $("#jsonstats").html(html_pretty);

    t = Date.parse(data["time"]);
    ts = new Date(t);
    updatePacketData(packets_chart, ts, stats["PacketList"]["tx"], stats["PacketList"]["rx"]);
    updatePacketTypesData(ts, stats["PacketList"]["types"]);
    updatePacketTypesChart();
    updateMessagesChart();
    updateAcksChart();
    updateMemChart(ts, stats["APRSDStats"]["memory_current"], stats["APRSDStats"]["memory_peak"]);
    updateThreadChart(ts, stats["APRSDThreadList"]);
    //updateQuadData(message_chart, short_time, data["stats"]["messages"]["sent"], data["stats"]["messages"]["received"], data["stats"]["messages"]["ack_sent"], data["stats"]["messages"]["ack_recieved"]);
    //updateDualData(email_chart, short_time, data["stats"]["email"]["sent"], data["stats"]["email"]["recieved"]);
    //updateDualData(memory_chart, short_time, data["stats"]["aprsd"]["memory_peak"], data["stats"]["aprsd"]["memory_current"]);
}
