# Tests to check DB and data filling and fetching
import os
import sys
from sqlalchemy.engine.row import RowMapping

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from decorators import PAGINATION_DEFAULT_ITEMS_PER_PAGE
from db import DQM2MirrorDB

# Needed to be passed as a fixture
from fixtures import db_test_db, get_valid_metadata


class TestPagination:
    def test_fill_and_get_lotsa_items_w_pagination(self, db_test_db: DQM2MirrorDB):
        MULTIPLE_OF_ITEMS_PER_PAGE = 2
        MAX_ELEMENTS = PAGINATION_DEFAULT_ITEMS_PER_PAGE * MULTIPLE_OF_ITEMS_PER_PAGE
        for i in range(0, MAX_ELEMENTS):
            db_test_db.fill_cmssw_comparison_report(
                **get_valid_metadata(i),
            )
        r = db_test_db.get_cmssw_comparison_reports(paginate=True)
        assert isinstance(r, dict)
        assert all(r and [key in r for key in ["page", "total_pages"]])
        assert (
            r["page"] == 1
            and r["total_pages"] == MULTIPLE_OF_ITEMS_PER_PAGE
            and isinstance(r["data"], list)
            and isinstance(r["data"][0], RowMapping)
        )
        r2 = db_test_db.get_cmssw_comparison_reports(paginate=True, page=1)
        assert r == r2
        r3 = db_test_db.get_cmssw_comparison_reports(paginate=True, page=2)
        assert r3["page"] == 2 and r3["total_pages"] == MULTIPLE_OF_ITEMS_PER_PAGE

    def test_fill_and_get_lotsa_items_no_pagination(self, db_test_db: DQM2MirrorDB):
        MULTIPLE_OF_ITEMS_PER_PAGE = 2
        MAX_ELEMENTS = PAGINATION_DEFAULT_ITEMS_PER_PAGE * MULTIPLE_OF_ITEMS_PER_PAGE
        for i in range(0, MAX_ELEMENTS):
            db_test_db.fill_cmssw_comparison_report(
                **get_valid_metadata(i),
            )
        r = db_test_db.get_cmssw_comparison_reports(paginate=False)
        assert all(isinstance(_, RowMapping) for _ in r)
        assert r and isinstance(r, list)
        assert len(r) == MAX_ELEMENTS
