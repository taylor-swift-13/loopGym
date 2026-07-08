int unknown();
void foo274() {

    int i;
    int k;
    int n;

    i = 0;
    k = 0;


        n = unknown();

    while (i < n) {
       i = i + 1;
       k = k + 1;
      }

    /*@ assert k >= n; */

  }