var cleared = false;

function size_dict(d){c=0; for (i in d) ++c; return c}

function init_messages() {
   const socket = io("/sendmsg");
   socket.on('connect', function () {
       console.log("Connected to socketio");
   });
   socket.on('connected', function(msg) {
       console.log("Connected!");
       console.log(msg);
   });

   socket.on("sent", function(msg) {
       if (cleared == false) {
           var msgsdiv = $("#msgsDiv");
           msgsdiv.html('')
           cleared = true
       }
       add_msg(msg);
   });

   socket.on("ack", function(msg) {
       update_msg(msg);
   });
   socket.on("reply", function(msg) {
       update_msg(msg);
   });

}

function add_msg(msg) {
    var msgsdiv = $("#sendMsgsDiv");

    ts_str = msg["ts"].toString();
    ts = ts_str.split(".")[0]*1000;
    var d = new Date(ts).toLocaleDateString("en-US")
    var t = new Date(ts).toLocaleTimeString("en-US")

    from = msg['from']
    title_id = 'title_tx'
    var from_to = d + " " + t + "&nbsp;&nbsp;&nbsp;&nbsp;" + from + " > "

    if (msg.hasOwnProperty('to')) {
        from_to = from_to + msg['to']
    }
    from_to = from_to + "&nbsp;&nbsp;-&nbsp;&nbsp;" + msg['message']

    id = ts_str.split('.')[0]
    pretty_id = "pretty_" + id
    loader_id = "loader_" + id
    ack_id = "ack_" + id
    reply_id = "reply_" + id
    span_id = "span_" + id
    json_pretty = Prism.highlight(JSON.stringify(msg, null, '\t'), Prism.languages.json, 'json');
    var unique_id = 'msg-accordion-' + id;
    msg_html = '<div class="accordion-item">' +
        '<div class="accordion-header" id="' + unique_id + '-header" onclick="toggleAccordion(\'' + unique_id + '\')">' +
        '<span class="accordion-icon material-symbols-rounded">chevron_right</span>' +
        '<div id="' + title_id + '">' +
        '<span class="material-symbols-rounded" style="font-size: 1rem;">hourglass_empty</span>&nbsp;' +
        '<span class="material-symbols-rounded" id="' + ack_id + '" style="font-size: 1rem;">thumb_down</span>&nbsp;' +
        '<span class="material-symbols-rounded" id="' + reply_id + '" style="font-size: 1rem;">thumb_down</span>&nbsp;' +
        '<span id="' + span_id + '">' + from_to +'</span>' +
        '</div>' +
        '</div>' +
        '<div class="accordion-content" id="' + unique_id + '-content">' +
        '<pre id="' + pretty_id + '" class="language-json">' + json_pretty + '</pre>' +
        '</div>' +
        '</div>';
    msgsdiv.prepend(msg_html);
}

function update_msg(msg) {
   var msgsdiv = $("#sendMsgsDiv");
    // We have an existing entry
    ts_str = msg["ts"].toString();
    id = ts_str.split('.')[0]
    pretty_id = "pretty_" + id
    loader_id = "loader_" + id
    reply_id = "reply_" + id
    ack_id = "ack_" + id
    span_id = "span_" + id



    if (msg['ack'] == true) {
        var loader_div = $('#' + loader_id);
        var ack_div = $('#' + ack_id);
        if (loader_div.length) {
            loader_div.remove();
        }
        if (ack_div.length) {
            ack_div.removeClass('thumb_down');
            ack_div.addClass('thumb_up');
            ack_div.attr('title', 'ACK Received');
        }
    }

    if (msg['reply'] !== null) {
        var reply_div = $('#' + reply_id);
        if (reply_div.length) {
            reply_div.removeClass("thumb_down");
            reply_div.addClass('reply');
            reply_div.attr('title', 'Got Reply');
        }

        var d = new Date(ts).toLocaleDateString("en-US")
        var t = new Date(ts).toLocaleTimeString("en-US")
        var from_to = d + " " + t + "&nbsp;&nbsp;&nbsp;&nbsp;" + from + " > "

        if (msg.hasOwnProperty('to')) {
            from_to = from_to + msg['to']
        }
        from_to = from_to + "&nbsp;&nbsp;-&nbsp;&nbsp;" + msg['message']
        from_to += "&nbsp;&nbsp; ===> " + msg["reply"]["message_text"]

        var span_div = $('#' + span_id);
        span_div.html(from_to);
    }

    var pretty_pre = $("#" + pretty_id);
    if (pretty_pre.length) {
        pretty_pre.html('');
        json_pretty = Prism.highlight(JSON.stringify(msg, null, '\t'), Prism.languages.json, 'json');
        pretty_pre.html(json_pretty);
    }
}
