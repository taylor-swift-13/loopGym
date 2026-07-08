/*@ requires n <= 20000001; */
void foo315(unsigned int n) {
    unsigned int j;
    unsigned int i;
    unsigned int k;

    i = 0;
    k = 0;
    j = 0;


    while (i < n) {
       i = i + 3;
       j = j + 3;
       k = k + 3;
      }

    /*@ assert k == j; */

  }