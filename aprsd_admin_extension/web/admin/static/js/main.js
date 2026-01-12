// watchlist is a dict of ham callsign => symbol, packets
var watchlist = {};
var our_callsign = "";

function aprs_img(item, x_offset, y_offset) {
    var x = x_offset * -16;
    if (y_offset > 5) {
        y_offset = 5;
    }
    var y = y_offset * -16;
    var loc = x + 'px '+ y + 'px'
    item.css('background-position', loc);
}

function show_aprs_icon(item, symbol) {
    var offset = ord(symbol) - 33;
    var col = Math.floor(offset / 16);
    var row = offset % 16;
    //console.log("'" + symbol+"'   off: "+offset+"  row: "+ row + "   col: " + col)
    aprs_img(item, row, col);
}

function ord(str){return str.charCodeAt(0);}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    var map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Accordion toggle function
function toggleAccordion(id) {
    var content = document.getElementById(id + '-content');
    var header = document.getElementById(id + '-header');
    var icon = header.querySelector('.accordion-icon');

    if (content.classList.contains('active')) {
        content.classList.remove('active');
        header.classList.remove('active');
        icon.style.transform = 'rotate(0deg)';
    } else {
        content.classList.add('active');
        header.classList.add('active');
        icon.style.transform = 'rotate(90deg)';
    }
}


function update_watchlist( data ) {
    // Update the watch list
    stats = data["stats"];
    if (stats.hasOwnProperty("WatchList") == false) {
        return
    }
    var watchdiv = $("#watchDiv");
    var html_str = '<table class="table table-striped"><thead><tr><th>HAM Callsign</th><th>Age since last seen by APRSD</th></tr></thead><tbody>'
    watchdiv.html('')
    jQuery.each(stats["WatchList"], function(i, val) {
        html_str += '<tr><td><img id="callsign_'+i+'" class="aprsd_1"></img>' + i + '</td><td>' + val["last"] + '</td></tr>'
    });
    html_str += "</tbody></table>";
    watchdiv.append(html_str);

    jQuery.each(watchlist, function(i, val) {
        //update the symbol
        var call_img = $('#callsign_'+i);
        show_aprs_icon(call_img, val['symbol'])
    });
}

function update_watchlist_from_packet(callsign, val) {
    if (!watchlist.hasOwnProperty(callsign)) {
        watchlist[callsign] = {
            "symbol": '[',
            "packets": {},
        }
    } else {
        if (val.hasOwnProperty('symbol')) {
            //console.log("Updating symbol for "+callsign + " to "+val["symbol"])
            watchlist[callsign]["symbol"] = val["symbol"]
        }
    }
    if (watchlist[callsign]["packets"].hasOwnProperty(val['ts']) == false) {
        watchlist[callsign]["packets"][val['ts']]= val;
    }
    //console.log(watchlist)
}

function update_seenlist( data ) {
    stats = data["stats"];
    if (stats.hasOwnProperty("SeenList") == false) {
        return
    }
    var seendiv = $("#seenDiv");
    var html_str = '<table class="table table-striped">'
    html_str    += '<thead><tr><th>HAM Callsign</th><th>Age since last seen by APRSD</th>'
    html_str    += '<th>Number of packets RX</th></tr></thead><tbody>'
    seendiv.html('')
    var seen_list = stats["SeenList"]
    var len = Object.keys(seen_list).length
    $('#seen_count').html(len)
    jQuery.each(seen_list, function(i, val) {
        html_str += '<tr><td>'
        html_str += '<img id="callsign_'+i+'" class="aprsd_1"></img>' + i + '</td>'
        html_str += '<td>' + val["last"] + '</td>'
        html_str += '<td>' + val["count"] + '</td></tr>'
    });
    html_str += "</tbody></table>";
    seendiv.append(html_str);
}

function update_plugins( data ) {
    stats = data["stats"];
    if (stats.hasOwnProperty("PluginManager") == false) {
        return
    }
    var plugindiv = $("#pluginDiv");
    var html_str = '<table class="table table-striped"><thead><tr>'
    html_str +=      '<th>Plugin Name</th><th>Plugin Enabled?</th>'
    html_str +=      '<th>Processed Packets</th><th>Sent Packets</th>'
    html_str +=      '<th>Version</th>'
    html_str +=    '</tr></thead><tbody>'
    plugindiv.html('')

    var plugins = stats["PluginManager"];
    var keys = Object.keys(plugins);
    keys.sort();
    for (var i=0; i<keys.length; i++) { // now lets iterate in sort order
        var key = keys[i];
        var val = plugins[key];
        html_str += '<tr><td>' + key + '</td>';
        html_str += '<td>' + val["enabled"] + '</td><td>' + val["rx"] + '</td>';
        html_str += '<td>' + val["tx"] + '</td><td>' + val["version"] +'</td></tr>';
    }
    html_str += "</tbody></table>";
    plugindiv.append(html_str);
}

function update_threads( data ) {
    stats = data["stats"];
    if (stats.hasOwnProperty("APRSDThreadList") == false) {
        return
    }
    var threadsdiv = $("#threadsDiv");
    var countdiv = $("#thread_count");
    var html_str = '<table class="table table-striped"><thead><tr>'
    html_str +=      '<th>Thread Name</th><th>Alive?</th>'
    html_str +=      '<th>Age</th><th>Loop Count</th>'
    html_str +=    '</tr></thead><tbody>'
    threadsdiv.html('')

    var threads = stats["APRSDThreadList"];
    var keys = Object.keys(threads);
    countdiv.html(keys.length);
    keys.sort();
    for (var i=0; i<keys.length; i++) { // now lets iterate in sort order
        var key = keys[i];
        var val = threads[key];
        html_str += '<tr><td>' + key + '</td>';
        html_str += '<td>' + val["alive"] + '</td><td>' + val["age"] + '</td>';
        html_str += '<td>' + val["loop_count"] + '</td></tr>';
    }
    html_str += "</tbody></table>";
    threadsdiv.append(html_str);
}

function update_packets( data ) {
    var packetsdiv = $("#packetsDiv");
    //nuke the contents first, then add to it.
    if (size_dict(packet_list) == 0 && size_dict(data) > 0) {
        packetsdiv.html('')
    }
    //console.log( "Update packets called " + Object.keys( data.packets ).length ) ;
    jQuery.each(data.packets, function(i, val) {
        pkt = val;

        update_watchlist_from_packet(pkt['from_call'], pkt);
        if ( packet_list.hasOwnProperty(pkt['timestamp']) == false ) {
            // Store the packet
            packet_list[pkt['timestamp']] = pkt;
            //ts_str = val["timestamp"].toString();
            //ts = ts_str.split(".")[0]*1000;
            ts = pkt['timestamp'] * 1000;
            var from_call = pkt.from_call || '';
            var to_call = pkt.to_call || '';
            var packet_type = pkt._type || 'Packet';
            var msg_no = pkt.msgNo || '';
            var is_tx = (from_call == our_callsign);

            if (is_tx) {
                title_id = 'title_tx';
            } else {
                title_id = 'title_rx';
            }

            // Format like log.py compact format: RX↓ PacketType:msgNo from_call → to_call : message
            var compact_line = '';
            if (is_tx) {
                compact_line += '<span class="packet-tx">TX</span><span class="packet-arrow">↑</span> ';
            } else {
                compact_line += '<span class="packet-rx">RX</span><span class="packet-arrow">↓</span> ';
            }

            compact_line += '<span class="packet-type">' + escapeHtml(packet_type) + '</span>';
            if (msg_no) {
                compact_line += ':<span class="packet-msgno">' + escapeHtml(String(msg_no)) + '</span>';
            }

            compact_line += ' <span class="packet-from">' + escapeHtml(from_call) + '</span> <span class="packet-arrow">→</span> ';

            // Add path if available
            if (pkt.path && Array.isArray(pkt.path) && pkt.path.length > 0) {
                compact_line += '<span class="packet-path">' + escapeHtml(pkt.path.join('→')) + '</span><span class="packet-arrow">→</span> ';
            }

            compact_line += '<span class="packet-to">' + escapeHtml(to_call) + '</span>';

            // Add message if available
            if (pkt.human_info || pkt.message_text) {
                var msg = pkt.human_info || pkt.message_text || '';
                if (msg) {
                    compact_line += ' : <span class="packet-message">' + escapeHtml(msg) + '</span>';
                }
            }

            json_pretty = Prism.highlight(JSON.stringify(pkt, null, '\t'), Prism.languages.json, 'json');
            var unique_id = 'accordion-' + pkt['timestamp'];
            pkt_html = '<div class="accordion-item compact-accordion">' +
                '<div class="accordion-header compact-header" id="' + unique_id + '-header" onclick="toggleAccordion(\'' + unique_id + '\')">' +
                '<span class="accordion-icon material-symbols-rounded">chevron_right</span>' +
                '<div class="packet-line" id="' + title_id + '">' + compact_line + '</div>' +
                '</div>' +
                '<div class="accordion-content" id="' + unique_id + '-content">' +
                '<pre class="language-json">' + json_pretty + '</pre>' +
                '</div>' +
                '</div>';
            packetsdiv.prepend(pkt_html);
        }
    });

    // Update the count of messages shown
    cnt = size_dict(packet_list);
    //console.log("packets list " + cnt)
    $('#packets_count').html(cnt);

    const html_pretty = Prism.highlight(JSON.stringify(data, null, '\t'), Prism.languages.json, 'json');
    $("#packetsjson").html(html_pretty);
}


function start_update() {

    (function statsworker() {
            $.ajax({
                url: "/stats",
                type: 'GET',
                dataType: 'json',
                success: function(data) {
                    update_stats(data);
                    update_watchlist(data);
                    update_seenlist(data);
                    update_plugins(data);
                    update_threads(data);
                },
                complete: function() {
                    setTimeout(statsworker, 10000);
                }
            });
    })();

    (function packetsworker() {
        $.ajax({
            url: "/packets",
            type: 'GET',
            dataType: 'json',
            success: function(data) {
                update_packets(data);
            },
            complete: function() {
                setTimeout(packetsworker, 10000);
            }
        });
    })();
}
