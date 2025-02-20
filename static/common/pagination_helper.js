/*
    Pagination helper for splitting array-like data into pages
    and showing a page index to browse it.

    This implementation assumes that all the data paginated
    by the API.
*/
function pagination_helper(dom_element, item_creation_callback, next_page_callback, items_per_page) {
    let _current_page = 1;
    let _data = {}
    let _dom_element = '';  // The DOM element where the data will be put in
    let _items_per_page = 1;
    let _total_pages = 1;
    let _item_creation_callback; /* Callback to run on each li item creation */
    let _next_page_callback; /* Callback to run on every page number click */
    let _unique_id = (Math.random() + 1).toString(36).substring(7);/* Random id to give to elements */
    let _is_initialized = false;
    const NUM_PAGES_SHOW_ELLIPSIS = 2

    _initialize(dom_element, item_creation_callback, next_page_callback, items_per_page)


    // Called when the object is instantiated.
    function _initialize(dom_element, item_creation_callback, next_page_callback, items_per_page) {
        _is_initialized = true
        _dom_element = dom_element;
        _items_per_page = Number(items_per_page)
        if (isNaN(_items_per_page)) {
            throw Error(`items_per_page should be a number, received ${typeof items_per_page}: ${items_per_page}`)
        }

        if (typeof item_creation_callback === 'function') {
            _item_creation_callback = item_creation_callback
        }
        if (typeof next_page_callback === 'function') {
            _next_page_callback = next_page_callback
        }
        _is_initialized = true
    }

    function _set_total_pages(num_pages) {
        _total_pages = num_pages
    }

    /* Helper function for adding CSS classes to a paginator page button */
    function _add_bootstrap_classes_to_page_li(el) {
        el.classList.add('page-item')
        el.firstChild.classList.add('page-link')
        return el
    }

    /* Callback to run when clicking the next page button */
    function _goto_next_page() {
        if (_current_page + 1 > _total_pages) {
            _current_page = _total_pages;
        }
        else {
            _current_page += 1;
        }
        _goto_specific_page(_current_page)
    }

    /* Callback to run when clicking the previous page button */
    function _goto_prev_page() {
        if (_current_page - 1 < 1) {
            _current_page = 1;
        }
        else {
            _current_page -= 1;
        }
        _goto_specific_page(_current_page)
    }

    /* To be run on any page change */
    function _on_page_change() {
        _clear_paginator()
        _create_paginator_buttons()
        _clear_page_data()
        _fill_page_data()
    }

    /* Callback to run when clicking on a page button */
    function _goto_specific_page(page_num) {
        if (page_num <= _total_pages && page_num >= 1) {
            _current_page = page_num;
            if (typeof _next_page_callback === 'function') {
                _next_page_callback(page_num)
            }
            _on_page_change()
        }
    }

    /*
    Function that crates a paginator button for a single page.

    content: can be either a DOM Element (in which case it is appended directly
    into the button), or a text/number, in which case it replaces the innerHTML.

    additional classes: a string of CSS classes to be added to the button (e.g., "class1 class2")

    onclick: the function to run when the button is clicked. It will be passed the
    DOM Element as an argument.

    title: the string to display on button mouse hover.
     */
    function _create_pagination_button(content, additional_classes, onclick, title) {
        let li = document.createElement('li')
        if (additional_classes && additional_classes instanceof Array) {
            li.classList.add(...additional_classes)
        }
        else if (additional_classes && typeof additional_classes === 'string') {
            li.classList.add(additional_classes)
        }

        let a = document.createElement('a')
        a.setAttribute.href = '#'
        if (content instanceof Element) {
            a.appendChild(content)
        }
        else if (typeof content === 'number') {/* If the content is a number, it's probably a page number */
            a.innerHTML = String(content)
            if (!title) {
                li.setAttribute('title', `Go to page ${content}`)
            }
        }
        else if (typeof content !== "undefined" && title !== null) {
            a.innerHTML = String(content)
            if (typeof title !== "undefined" && title !== null) {
                li.setAttribute('title', title)
            }
        }

        if (typeof onclick === 'function') {
            li.onclick = onclick
        }
        li.appendChild(a)
        return _add_bootstrap_classes_to_page_li(li)
    }

    function _create_first_page_el() {
        let i = document.createElement('i')
        i.classList.add('bi', 'bi-chevron-double-left')

        return _create_pagination_button(i, _current_page === 1 ? "disabled" : "",
            () => { _goto_specific_page(1) }, "First page")
    }

    function _create_previous_page_el() {
        let i = document.createElement('i')
        i.classList.add('bi', 'bi-chevron-left')
        return _create_pagination_button(i, _current_page === 1 ? "disabled" : "",
            _goto_prev_page, "Previous page")
    }

    function _create_last_page_el() {
        let i = document.createElement('i')
        i.classList.add('bi', 'bi-chevron-double-right')
        return _create_pagination_button(i, (_current_page === _total_pages || _total_pages === 0) ?
            "disabled" : "",
            () => { _goto_specific_page(_total_pages) },
            'Last page')
    }

    function _create_next_page_el() {
        let i = document.createElement('i')
        i.classList.add('bi', 'bi-chevron-right')
        return _create_pagination_button(i, (_current_page === _total_pages || _total_pages === 0) ?
            "disabled" : "",
            _goto_next_page,
            "Next page")
    }

    /* Create a single page button for a specific page */
    function _create_page_number_el(page_num) {
        return _create_pagination_button(
            page_num,
            _current_page === page_num ? "active" : "",
            () => { _goto_specific_page(page_num) }
        )
    }

    /* Get the DOM element id where page buttons will be added */
    function _get_pagination_el_id() {
        return `${_dom_element}-pagination-${_unique_id}`
    }

    /* Clear the pagination buttons completely */
    function _clear_paginator() {
        let pagination_el = document.getElementById(_get_pagination_el_id())
        if (pagination_el) {
            pagination_el.innerHTML = ''
        }
    }

    /*
    Create the pagination element under the same parent as the
    _dom_element passed at initialization.
    */
    function _create_pagination_el() {
        let pagination_el = document.getElementById(_get_pagination_el_id())
        let pagination_el_exists = true
        if (!pagination_el) {
            pagination_el = document.createElement('nav');
            pagination_el_exists = false
        }
        else {
            pagination_el.innerHTML = ""
        }


        let ul_el = document.createElement('ul');
        ul_el.classList.add('pagination', 'mt-2')
        ul_el.setAttribute('id', _get_pagination_el_id())
        pagination_el.appendChild(ul_el)
        if (!pagination_el_exists) {
            let base_el = document.getElementById(_dom_element).parentElement;
            base_el.appendChild(pagination_el);
        }
    }

    /*
        Create the page links inside the pagination DOM element.
    */
    function _create_paginator_buttons() {
        let pagination_el = document.getElementById(_get_pagination_el_id())
        pagination_el.appendChild(_create_first_page_el())
        pagination_el.appendChild(_create_previous_page_el())
        if (_total_pages < 3) {
            for (i = 1; i <= _total_pages; i++) {
                pagination_el.appendChild(_create_page_number_el(i))
            }
        }
        else {
            if (_current_page - 1 <= NUM_PAGES_SHOW_ELLIPSIS) {
                for (let i = 1; i <= _current_page - 1; i++) {
                    pagination_el.appendChild(_create_page_number_el(i))
                }
            }
            else {
                pagination_el.appendChild(_create_pagination_button('...', 'disabled', null, ''))
                pagination_el.appendChild(_create_page_number_el(_current_page - 1))
            }

            pagination_el.appendChild(_create_page_number_el(_current_page))

            if (_total_pages - _current_page <= NUM_PAGES_SHOW_ELLIPSIS) {
                for (let i = _current_page + 1; i <= _total_pages; i++) {
                    pagination_el.appendChild(_create_page_number_el(i))
                }
            }
            else {
                pagination_el.appendChild(_create_page_number_el(_current_page + 1))
                pagination_el.appendChild(_create_pagination_button('...', 'disabled', null, ''))

            }
        }
        pagination_el.appendChild(_create_next_page_el())
        pagination_el.appendChild(_create_last_page_el())
    }

    // Create a single li element for a single comparison report.
    function _create_result_list_element(data) {
        let li = document.createElement("li");

        if (typeof _item_creation_callback === 'function') {
            li = _item_creation_callback(li, data)
        }
        return li;
    }

    function _clear_page_data() {
        let data_el = document.getElementById(_dom_element)
        data_el.innerHTML = ''
    }
    function _fill_page_data() {
        let data_el = document.getElementById(_dom_element)
        _data.forEach(element => {
            data_el.appendChild(_create_result_list_element(element))
        });
    }

    function _set_data(data, page, total_pages) {
        if (!_is_initialized) {
            throw Error(`Paginator has not been initialized!`)
        }
        if (typeof data !== 'object' || !data.hasOwnProperty('length')) {
            throw Error(`data passed should be array-like, cannot initialize pagination`)
        }
        _data = data;
        _num_total_items = data.length;
        if (typeof dom_element !== 'string' || !document.getElementById(dom_element)) {
            throw Error(`Could not find DOM element "${dom_element}" to attach pagination to`)
        }
        _current_page = page
        _set_total_pages(total_pages)
        _create_pagination_el()
        _on_page_change()

    }
    /* "Public" methods are returned as an object with functions */
    return {
        set_data: (data, page, total_pages) => {
            _set_data(data, page, total_pages)
        }
    }
};