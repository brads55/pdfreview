/*
 * Javascript functions to help with ui-related matters.
 * Many of these functions are adopted from the pdf.js example code.
 * Francois Botman, 2017.
 */

/**
 * Helper function to start monitoring the scroll event and converting them into
 * PDF.js friendly one: with scroll debounce and scroll direction.
 */
function watchScroll(viewAreaElement, callback) {
    var lastY = viewAreaElement.scrollTop;
    var rAF = null;
    
    var viewAreaElementScrolled = function viewAreaElementScrolled() {
        var currentY  = viewAreaElement.scrollTop;
        var previousY = lastY;
        lastY = currentY;
        // Only redraw if the scroll amount is not a "big scroll" event.
        if(Math.abs(currentY - previousY) < 1000) {
            rAF = null;
            callback();
        }
        else rAF = window.setTimeout(viewAreaElementScrolled, 100);
    }
    
    var debounceScroll = function debounceScroll(evt) {
        if (rAF) return;
        // Set a timer to invoke a redraw. The greater the timer the lower the UI latency will be, but also the
        // longer the user will have to wait for something to appear. As we preload pages, normal scrolling should
        // still appear responsive. The 100ms value was obtained by trial and error on a medium-range laptop.
        rAF = window.setTimeout(viewAreaElementScrolled, 100);
    };


  viewAreaElement.addEventListener('scroll', debounceScroll, true);
}


/**
 * Use binary search to find the index of the first item in a given array which
 * passes a given condition. The items are expected to be sorted in the sense
 * that if the condition is true for one item in the array, then it is also true
 * for all following items.
 *
 * @returns {Number} Index of the first array element to pass the test,
 *                   or |items.length| if no such element exists.
 */
function binarySearchFirstItem(items, condition) {
  var minIndex = 0;
  var maxIndex = items.length - 1;

  if (items.length === 0 || !condition(items[maxIndex])) {
    return items.length;
  }
  if (condition(items[minIndex])) {
    return minIndex;
  }

  while (minIndex < maxIndex) {
    var currentIndex = (minIndex + maxIndex) >> 1;
    var currentItem = items[currentIndex];
    if (condition(currentItem)) {
      maxIndex = currentIndex;
    } else {
      minIndex = currentIndex + 1;
    }
  }
  return minIndex; /* === maxIndex */
}

/**
 * Generic helper to find out what elements are visible within a scroll pane.
 */
function getVisibleElements(scrollEl, potentialDivs, sortByVisibility) {
  var top = scrollEl.scrollTop, bottom = top + scrollEl.clientHeight;
  var left = scrollEl.scrollLeft, right = left + scrollEl.clientWidth;

  function isElementBottomBelowViewTop(element) {
    var elementBottom =
      element.offsetTop + element.clientTop + element.clientHeight;
    return elementBottom > top;
  }

  var visible = [], element;
  var currentHeight, viewHeight, hiddenHeight, percentHeight;
  var currentWidth, viewWidth;
  var firstVisibleElementInd = (potentialDivs.length === 0) ? 0 :
    binarySearchFirstItem(potentialDivs, isElementBottomBelowViewTop);

  for (var i = firstVisibleElementInd, ii = potentialDivs.length; i < ii; i++) {
    element = potentialDivs[i];
    currentHeight = element.offsetTop + element.clientTop;
    viewHeight = element.clientHeight;

    if (currentHeight > bottom) break;

    currentWidth = element.offsetLeft + element.clientLeft;
    viewWidth = element.clientWidth;
    if (currentWidth + viewWidth < left || currentWidth > right) {
      continue;
    }
    hiddenHeight = Math.max(0, top - currentHeight) +
      Math.max(0, currentHeight + viewHeight - bottom);
    percentHeight = ((viewHeight - hiddenHeight) * 100 / viewHeight) | 0;

    visible.push({
      id: i,
      x: currentWidth,
      y: currentHeight,
      view: element,
      percent: percentHeight
    });
  }

  var first = visible[0];
  var last = visible[visible.length - 1];

  if (sortByVisibility) {
    visible.sort(function(a, b) {
      var pc = a.percent - b.percent;
      if (Math.abs(pc) > 0.001) {
        return -pc;
      }
      return a.id - b.id; // ensure stability
    });
  }
  return {first: first, last: last, views: visible};
}
