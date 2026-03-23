// ============================================================
// STATE
// ============================================================
const SOURCES_ALL = ['arxiv','semantic_scholar','huggingface','twitter'];
const TAG_PALETTE = [
  {bg:'rgba(124,106,247,0.15)',color:'#a99bf9',border:'rgba(124,106,247,0.38)'},
  {bg:'rgba(247,106,106,0.15)',color:'#f78f8f',border:'rgba(247,106,106,0.38)'},
  {bg:'rgba(247,183,106,0.15)',color:'#f7b76a',border:'rgba(247,183,106,0.38)'},
  {bg:'rgba(106,247,160,0.15)',color:'#6af7a0',border:'rgba(106,247,160,0.38)'},
  {bg:'rgba(106,212,247,0.15)',color:'#6ad4f7',border:'rgba(106,212,247,0.38)'},
  {bg:'rgba(247,106,240,0.15)',color:'#f76af0',border:'rgba(247,106,240,0.38)'},
  {bg:'rgba(247,224,106,0.15)',color:'#f7e06a',border:'rgba(247,224,106,0.38)'},
];
const chipData = {topics:[],keywords:[],authors:[],venues:[]};
let allPapers = [];
let myListState = {};
let crawlHistory = [];
let crawlChart = null;
let pollTimer = null;
let activeTagFilters = new Set();
let activeSourceFilters = new Set();
let expandedCards = new Set();
